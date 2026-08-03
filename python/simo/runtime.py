"""Process lifecycle owners for deterministic and live Simo modes."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Iterable

from pipecat.frames.frames import LLMTextFrame, TTSAudioRawFrame

from simo.adapters.pipecat.deterministic import run_deterministic_pipeline
from simo.config import RuntimeConfig
from simo.context import NativeContextEngine
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
            with NativeContextEngine(
                queue_capacity=self._config.queue_capacity,
                max_segments=self._config.max_segments,
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
