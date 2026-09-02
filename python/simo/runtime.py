"""Process lifecycle owners for deterministic and live Simo modes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from pipecat.frames.frames import LLMTextFrame, TTSAudioRawFrame

from simo.adapters.pipecat.deterministic import run_deterministic_pipeline
from simo.config import RuntimeConfig
from simo.context import ConversationContextScope, NativeContextEngine
from simo.knowledge import refresh_knowledge_graph
from simo.operations import NullEventSink, OperationalEventSink, RuntimeMetrics


@dataclass(frozen=True, slots=True)
class HeadlessResult:
    snapshot: dict[str, object]
    stats: dict[str, int]
    pipeline: dict[str, int]
    knowledge: dict[str, int]
    operations: dict[str, object]


class HeadlessRuntime:
    """Own the native world for one deterministic no-model execution."""

    def __init__(
        self,
        config: RuntimeConfig,
        *,
        events: OperationalEventSink | None = None,
    ) -> None:
        self._config = config
        self._events = events or NullEventSink()

    async def run(self, transcripts: Iterable[str]) -> HeadlessResult:
        selected = [text for text in transcripts if text.strip()]
        mode = "headless"
        metrics = RuntimeMetrics()
        metrics.transition("starting")
        self._events.lifecycle(mode, "starting")
        try:
            scope = ConversationContextScope.ephemeral(mode, "user")
            with NativeContextEngine(
                queue_capacity=self._config.queue_capacity,
                max_segments=self._config.max_segments,
                scope=scope,
                library_path=self._config.core_library,
            ) as engine:
                metrics.transition("ready")
                self._events.lifecycle(mode, "ready")
                knowledge_token = metrics.start_stage("knowledge")
                try:
                    knowledge = refresh_knowledge_graph(engine, self._config.repository)
                except Exception:
                    metrics.finish_stage(knowledge_token, error=True)
                    raise
                metrics.finish_stage(knowledge_token)

                pipeline_token = metrics.start_stage("pipeline")
                try:
                    result = await run_deterministic_pipeline(
                        engine,
                        selected,
                        max_prompt_chars=self._config.context_max_chars,
                        max_context_age_ms=self._config.context_max_age_ms,
                        metrics=metrics,
                    )
                except BaseException as error:
                    metrics.finish_stage(
                        pipeline_token,
                        error=not isinstance(error, asyncio.CancelledError),
                    )
                    raise
                metrics.finish_stage(pipeline_token)

                snapshot = engine.snapshot()
                engine_stats = engine.stats()
                stats = asdict(engine_stats)
                pipeline = {
                    "context_injections": result.injection_count,
                    "observation_accepted": result.observation_accepted,
                    "observation_duplicates": result.observation_duplicates,
                    "observation_mailbox_dropped": result.observer_mailbox_dropped,
                    "observation_mailbox_queued": result.observer_mailbox_queued,
                    "llm_text_frames": sum(
                        isinstance(frame, LLMTextFrame) for frame in result.frames
                    ),
                    "tts_audio_frames": sum(
                        isinstance(frame, TTSAudioRawFrame) for frame in result.frames
                    ),
                }
                knowledge_result = {
                    "revision": knowledge.revision,
                    "concepts": knowledge.concepts,
                    "links": knowledge.links,
                    "removed": knowledge.removed,
                }
                metrics.update_runtime_state(
                    world_revision=int(snapshot["revision"]),
                    context_queue_depth=engine_stats.queued,
                    context_queue_dropped=engine_stats.dropped,
                    context_accepted=engine_stats.accepted,
                    context_processed=engine_stats.processed,
                    context_retained=engine_stats.retained,
                    observer_mailbox_depth=result.observer_mailbox_queued,
                    observer_mailbox_dropped=result.observer_mailbox_dropped,
                )
            metrics.transition("stopping")
            self._events.lifecycle(mode, "stopping", reason="completed")
            metrics.stop("completed", clean=True)
            operations = metrics.snapshot()
            self._events.lifecycle(mode, "stopped", reason="completed")
            self._events.metrics(mode, operations)
            return HeadlessResult(
                snapshot=snapshot,
                stats=stats,
                pipeline=pipeline,
                knowledge=knowledge_result,
                operations=operations,
            )
        except asyncio.CancelledError:
            metrics.transition("stopping")
            self._events.lifecycle(mode, "stopping", reason="cancelled")
            metrics.stop("cancelled", clean=True)
            self._events.lifecycle(mode, "stopped", reason="cancelled")
            self._events.metrics(mode, metrics.snapshot())
            raise
        except Exception as error:
            if metrics.snapshot()["errors_total"] == 0:
                metrics.record_error()
            self._events.failure(mode, "runtime", error)
            metrics.transition("stopping")
            self._events.lifecycle(mode, "stopping", reason="failed")
            metrics.stop("failed", clean=False)
            self._events.lifecycle(mode, "stopped", reason="failed")
            self._events.metrics(mode, metrics.snapshot())
            raise


class LiveAudioTransport(Protocol):
    def input(self) -> Any: ...

    def output(self) -> Any: ...

    async def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class LiveResult:
    operations: dict[str, object]


class LiveRuntime:
    """Own one local microphone/speaker Pipecat session and Flecs world."""

    def __init__(
        self,
        config: RuntimeConfig,
        *,
        events: OperationalEventSink | None = None,
        transport_factory: Callable[[RuntimeConfig], LiveAudioTransport] | None = None,
        recognizer_factory: Callable[[RuntimeConfig], Any] | None = None,
        generator_factory: Callable[[RuntimeConfig], Any] | None = None,
        synthesizer_factory: Callable[[RuntimeConfig], Any] | None = None,
        runner_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._config = config
        self._events = events or NullEventSink()
        self._transport_factory = transport_factory or _create_local_transport
        self._recognizer_factory = recognizer_factory or _create_recognizer
        self._generator_factory = generator_factory or _create_generator
        self._synthesizer_factory = synthesizer_factory or _create_synthesizer
        self._runner_factory = runner_factory or _create_worker_runner

    async def run(self) -> LiveResult:
        from pipecat.audio.vad.vad_analyzer import VADParams
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.worker import PipelineParams, PipelineWorker

        from simo.adapters.pipecat.inference import (
            LocalSTTProcessor,
            LocalTextInferenceProcessor,
        )
        from simo.adapters.pipecat.local_audio import (
            ObservedSileroVADAnalyzer,
            PlaybackState,
            PlaybackStateProcessor,
            SileroUtteranceProcessor,
        )
        from simo.adapters.pipecat.observer import PipecatSemanticObserver
        from simo.adapters.pipecat.qwen_tts import QwenMLXTTSService
        from simo.adapters.pipecat.semantic_turn import SemanticTurnProcessor
        from simo.observation import (
            BoundedTranscriptMailbox,
            FinalTranscriptObservationBridge,
        )

        mode = "live"
        metrics = RuntimeMetrics()
        metrics.transition("starting")
        self._events.lifecycle(mode, "starting")
        transport: LiveAudioTransport | None = None
        try:
            scope = ConversationContextScope.ephemeral(mode, "local-user")
            with NativeContextEngine(
                queue_capacity=self._config.queue_capacity,
                max_segments=self._config.max_segments,
                scope=scope,
                library_path=self._config.core_library,
            ) as engine:
                knowledge_token = metrics.start_stage("knowledge")
                try:
                    refresh_knowledge_graph(engine, self._config.repository)
                except Exception:
                    metrics.finish_stage(knowledge_token, error=True)
                    raise
                metrics.finish_stage(knowledge_token)

                mailbox = BoundedTranscriptMailbox(capacity=self._config.queue_capacity)
                bridge = FinalTranscriptObservationBridge(mailbox)
                transport = self._transport_factory(self._config)
                playback_state = PlaybackState()
                segmenter = SileroUtteranceProcessor(
                    ObservedSileroVADAnalyzer(
                        runtime_metrics=metrics,
                        sample_rate=16_000,
                        params=VADParams(
                            confidence=self._config.vad_confidence,
                            start_secs=self._config.vad_start_ms / 1_000,
                            stop_secs=self._config.vad_stop_ms / 1_000,
                            min_volume=0.0,
                        ),
                    ),
                    pre_roll_ms=self._config.vad_pre_roll_ms,
                    max_utterance_s=self._config.max_utterance_s,
                    runtime_metrics=metrics,
                    playback_state=playback_state,
                )
                stt = LocalSTTProcessor(
                    self._recognizer_factory(self._config),
                    metrics=metrics,
                )
                semantic_turn = SemanticTurnProcessor(
                    engine,
                    bridge,
                    mailbox,
                    max_prompt_chars=self._config.context_max_chars,
                )
                text = LocalTextInferenceProcessor(
                    self._generator_factory(self._config),
                    max_tokens=self._config.text_max_tokens,
                    metrics=metrics,
                )
                tts = QwenMLXTTSService(
                    self._synthesizer_factory(self._config),
                    metrics=metrics,
                    model=self._config.tts.model_id,
                    voice=self._config.tts_voice,
                    sample_rate=24_000,
                )
                pipeline = Pipeline(
                    [
                        transport.input(),
                        segmenter,
                        stt,
                        semantic_turn,
                        text,
                        tts,
                        PlaybackStateProcessor(playback_state),
                        transport.output(),
                    ]
                )
                worker = PipelineWorker(
                    pipeline,
                    params=PipelineParams(
                        audio_in_sample_rate=16_000,
                        audio_out_sample_rate=24_000,
                    ),
                    observers=[PipecatSemanticObserver(bridge=bridge)],
                    enable_rtvi=False,
                    enable_turn_tracking=False,
                    idle_timeout_secs=None,
                )
                runner = self._runner_factory()
                await runner.add_workers(worker)
                metrics.transition("ready")
                self._events.lifecycle(mode, "ready")
                pipeline_token = metrics.start_stage("pipeline")
                try:
                    await runner.run()
                except BaseException as error:
                    metrics.finish_stage(
                        pipeline_token,
                        error=not isinstance(error, asyncio.CancelledError),
                    )
                    raise
                else:
                    metrics.finish_stage(pipeline_token)
                finally:
                    self._capture_live_state(metrics, engine, mailbox)
            if transport is not None:
                await transport.close()
                transport = None
            metrics.transition("stopping")
            self._events.lifecycle(mode, "stopping", reason="completed")
            metrics.stop("completed", clean=True)
            operations = metrics.snapshot()
            self._events.lifecycle(mode, "stopped", reason="completed")
            self._events.metrics(mode, operations)
            return LiveResult(operations)
        except asyncio.CancelledError:
            if transport is not None:
                await transport.close()
                transport = None
            metrics.transition("stopping")
            self._events.lifecycle(mode, "stopping", reason="cancelled")
            metrics.stop("cancelled", clean=True)
            self._events.lifecycle(mode, "stopped", reason="cancelled")
            self._events.metrics(mode, metrics.snapshot())
            raise
        except Exception as error:
            if transport is not None:
                await transport.close()
                transport = None
            if metrics.snapshot()["errors_total"] == 0:
                metrics.record_error()
            self._events.failure(mode, "runtime", error)
            metrics.transition("stopping")
            self._events.lifecycle(mode, "stopping", reason="failed")
            metrics.stop("failed", clean=False)
            self._events.lifecycle(mode, "stopped", reason="failed")
            self._events.metrics(mode, metrics.snapshot())
            raise
        finally:
            if transport is not None:
                await transport.close()

    @staticmethod
    def _capture_live_state(
        metrics: RuntimeMetrics,
        engine: NativeContextEngine,
        mailbox: Any,
    ) -> None:
        engine_stats = engine.stats()
        mailbox_stats = mailbox.stats()
        metrics.update_runtime_state(
            world_revision=int(engine.snapshot()["revision"]),
            context_queue_depth=engine_stats.queued,
            context_queue_dropped=engine_stats.dropped,
            context_accepted=engine_stats.accepted,
            context_processed=engine_stats.processed,
            context_retained=engine_stats.retained,
            observer_mailbox_depth=mailbox_stats.queued,
            observer_mailbox_dropped=mailbox_stats.dropped,
        )


def _create_local_transport(config: RuntimeConfig) -> LiveAudioTransport:
    from pipecat.transports.local.audio import LocalAudioTransportParams

    from simo.adapters.pipecat.local_audio import ManagedLocalAudioTransport

    return ManagedLocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=16_000,
            audio_out_sample_rate=24_000,
            input_device_index=config.audio_input_device_index,
            output_device_index=config.audio_output_device_index,
        )
    )


def _create_recognizer(config: RuntimeConfig) -> Any:
    from simo.inference import ParakeetMLXRecognizer

    return ParakeetMLXRecognizer(config.stt.local_path)


def _create_generator(config: RuntimeConfig) -> Any:
    from simo.inference import MLXTextGenerator

    return MLXTextGenerator(config.text.local_path)


def _create_synthesizer(config: RuntimeConfig) -> Any:
    from simo.config import TTSBackend
    from simo.inference import BreezeHTTPSynthesizer, MLXAudioSynthesizer

    if config.tts_backend is TTSBackend.BREEZE:
        return BreezeHTTPSynthesizer(
            config.tts_endpoint,
            instruction=config.tts_instruction,
            cfg_scale=config.tts_cfg_scale,
            seed=config.tts_seed,
            timeout_s=config.tts_timeout_s,
        )

    return MLXAudioSynthesizer(
        config.tts.local_path,
        voice=config.tts_voice,
        streaming_interval_s=config.tts_streaming_interval_s,
    )


def _create_worker_runner() -> Any:
    from pipecat.workers.runner import WorkerRunner

    return WorkerRunner(handle_sigint=False, handle_sigterm=False)
