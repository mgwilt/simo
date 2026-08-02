"""Pipecat observer that performs bounded semantic-event capture."""

from __future__ import annotations

from pipecat.frames.frames import InterimTranscriptionFrame, TranscriptionFrame
from pipecat.observers.base_observer import BaseObserver, FramePushed

from simo.observation import FinalTranscriptObservationBridge, TranscriptSink


class PipecatSemanticObserver(BaseObserver):
    """Observe final transcript frames without mutating Flecs or blocking the pipeline."""

    def __init__(self, sink: TranscriptSink, *, dedupe_capacity: int = 2_048) -> None:
        super().__init__()
        self._bridge = FinalTranscriptObservationBridge(
            sink,
            dedupe_capacity=dedupe_capacity,
        )

    @property
    def semantic_bridge(self) -> FinalTranscriptObservationBridge:
        return self._bridge

    async def on_push_frame(self, data: FramePushed) -> None:
        frame = data.frame
        if isinstance(frame, InterimTranscriptionFrame):
            return
        if not isinstance(frame, TranscriptionFrame):
            return
        frame_key = str(getattr(frame, "id", id(frame)))
        self._bridge.observe(
            frame_key=frame_key,
            speaker=frame.user_id,
            text=frame.text,
            is_final=True,
        )
