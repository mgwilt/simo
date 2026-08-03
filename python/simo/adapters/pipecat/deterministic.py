"""No-model Pipecat providers and acceptance-pipeline runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from pipecat.clocks.system_clock import SystemClock
from pipecat.frames.frames import (
    EndFrame,
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    StartFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    TTSTextFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frame_processor import (
    FrameDirection,
    FrameProcessor,
    FrameProcessorSetup,
)
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.text.base_text_aggregator import AggregationType

from simo.adapters.pipecat.observer import PipecatSemanticObserver
from simo.adapters.pipecat.semantic_turn import SemanticTurnFrame, SemanticTurnProcessor
from simo.context import NativeContextEngine
from simo.observation import BoundedTranscriptMailbox, FinalTranscriptObservationBridge
from simo.operations import RuntimeMetrics


class DeterministicTextInference(FrameProcessor):
    """Emit a stable response that demonstrably consumes semantic context."""

    def __init__(
        self,
        *,
        max_context_age_ms: int = 1_000,
        metrics: RuntimeMetrics | None = None,
    ) -> None:
        super().__init__(enable_direct_mode=True)
        self._max_context_age_ms = max_context_age_ms
        self._runtime_metrics = metrics
        self.turns: list[SemanticTurnFrame] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction is FrameDirection.DOWNSTREAM and isinstance(frame, SemanticTurnFrame):
            metrics = self._runtime_metrics
            token = metrics.start_stage("text_inference") if metrics else None
            try:
                frame.context.require_fresh(self._max_context_age_ms)
                self.turns.append(frame)
                response = (
                    f"Context revision {frame.context.revision} has "
                    f"{len(frame.context.items)} item(s). You said: {frame.user_text}"
                )
                await self.push_frame(LLMFullResponseStartFrame(), direction)
                await self.push_frame(LLMTextFrame(text=response), direction)
                await self.push_frame(LLMFullResponseEndFrame(), direction)
            except Exception:
                if metrics is not None and token is not None:
                    metrics.finish_stage(token, error=True)
                raise
            if metrics is not None and token is not None:
                metrics.finish_stage(token)
            return
        await self.push_frame(frame, direction)


class DeterministicTTS(FrameProcessor):
    """Turn LLM text into deterministic mono PCM frames without a model."""

    def __init__(
        self,
        *,
        sample_rate: int = 24_000,
        metrics: RuntimeMetrics | None = None,
    ) -> None:
        super().__init__(enable_direct_mode=True)
        self.sample_rate = sample_rate
        self._runtime_metrics = metrics

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)
        if direction is FrameDirection.DOWNSTREAM and isinstance(frame, LLMTextFrame):
            metrics = self._runtime_metrics
            token = metrics.start_stage("tts") if metrics else None
            try:
                samples = max(1, len(frame.text))
                await self.push_frame(
                    TTSAudioRawFrame(
                        audio=b"\x01\x00" * samples,
                        sample_rate=self.sample_rate,
                        num_channels=1,
                        context_id=str(frame.id),
                    ),
                    direction,
                )
                spoken = TTSTextFrame(
                    text=frame.text,
                    aggregated_by=AggregationType.SENTENCE,
                )
                spoken.will_be_spoken = True
                spoken.context_id = str(frame.id)
                await self.push_frame(spoken, direction)
                if metrics is not None and token is not None:
                    metrics.first_output(token)
            except Exception:
                if metrics is not None and token is not None:
                    metrics.finish_stage(token, error=True)
                raise
            if metrics is not None and token is not None:
                metrics.finish_stage(token)


class FrameCollector(FrameProcessor):
    def __init__(self) -> None:
        super().__init__(enable_direct_mode=True)
        self.frames: list[Frame] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction is FrameDirection.DOWNSTREAM:
            self.frames.append(frame)
        await self.push_frame(frame, direction)


@dataclass(frozen=True, slots=True)
class DeterministicPipelineResult:
    frames: tuple[Frame, ...]
    turns: tuple[SemanticTurnFrame, ...]
    injection_count: int
    observation_accepted: int
    observation_duplicates: int
    engine_revision: int
    engine_dropped: int
    observer_mailbox_dropped: int
    observer_mailbox_queued: int


async def run_deterministic_pipeline(
    engine: NativeContextEngine,
    transcripts: list[str],
    *,
    speaker_id: str = "user",
    max_prompt_chars: int = 8_000,
    max_context_age_ms: int = 1_000,
    metrics: RuntimeMetrics | None = None,
) -> DeterministicPipelineResult:
    """Run final transcripts through Pipecat, Flecs, fake LLM, and fake TTS."""

    mailbox = BoundedTranscriptMailbox()
    bridge = FinalTranscriptObservationBridge(mailbox)
    semantic_turn = SemanticTurnProcessor(
        engine,
        bridge,
        mailbox,
        max_prompt_chars=max_prompt_chars,
    )
    inference = DeterministicTextInference(
        max_context_age_ms=max_context_age_ms,
        metrics=metrics,
    )
    tts = DeterministicTTS(metrics=metrics)
    collector = FrameCollector()
    pipeline = Pipeline([semantic_turn, inference, tts, collector])
    clock = SystemClock()
    clock.start()
    setup = FrameProcessorSetup(
        clock=clock,
        task_manager=TaskManager(),
        pipeline_worker=cast("Any", object()),
        observer=PipecatSemanticObserver(bridge=bridge),
    )
    frames = [
        TranscriptionFrame(
            text=text,
            user_id=speaker_id,
            timestamp=f"turn-{index}",
            finalized=True,
        )
        for index, text in enumerate(transcripts, start=1)
    ]
    await pipeline.setup(setup)
    try:
        await pipeline.queue_frame(StartFrame())
        for frame in frames:
            await pipeline.queue_frame(frame)
        await pipeline.queue_frame(EndFrame())
    finally:
        await pipeline.cleanup()
    observation = bridge.stats()
    engine_stats = engine.stats()
    mailbox_stats = mailbox.stats()
    return DeterministicPipelineResult(
        frames=tuple(collector.frames),
        turns=tuple(inference.turns),
        injection_count=semantic_turn.injection_count,
        observation_accepted=observation.accepted,
        observation_duplicates=observation.duplicate,
        engine_revision=int(engine.snapshot()["revision"]),
        engine_dropped=engine_stats.dropped,
        observer_mailbox_dropped=mailbox_stats.dropped,
        observer_mailbox_queued=mailbox_stats.queued,
    )
