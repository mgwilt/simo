"""Pipecat frames and processors for Simo's replaceable local inference."""

from __future__ import annotations

from dataclasses import dataclass

from pipecat.frames.frames import (
    DataFrame,
    ErrorFrame,
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from simo.adapters.pipecat.semantic_turn import SemanticTurnFrame
from simo.inference import SpeechRecognizer, TextGenerator
from simo.operations import RuntimeMetrics


@dataclass
class PCMUtteranceFrame(DataFrame):
    audio: bytes
    sample_rate: int
    user_id: str
    timestamp: str


class LocalSTTProcessor(FrameProcessor):
    def __init__(
        self,
        recognizer: SpeechRecognizer,
        *,
        metrics: RuntimeMetrics | None = None,
    ) -> None:
        super().__init__(enable_direct_mode=True)
        self._recognizer = recognizer
        self._runtime_metrics = metrics

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction is FrameDirection.DOWNSTREAM and isinstance(
            frame, PCMUtteranceFrame
        ):
            metrics = self._runtime_metrics
            token = metrics.start_stage("stt") if metrics else None
            try:
                text = await self._recognizer.transcribe(frame.audio, frame.sample_rate)
            except Exception as error:
                if token:
                    metrics.finish_stage(token, error=True)
                await self.push_frame(
                    ErrorFrame(error=f"local STT failed: {error}", exception=error),
                    direction,
                )
                return
            if token:
                metrics.finish_stage(token)
            if text:
                await self.push_frame(
                    TranscriptionFrame(
                        text=text,
                        user_id=frame.user_id,
                        timestamp=frame.timestamp,
                        finalized=True,
                    ),
                    direction,
                )
            return
        await self.push_frame(frame, direction)


class LocalTextInferenceProcessor(FrameProcessor):
    def __init__(
        self,
        generator: TextGenerator,
        *,
        max_tokens: int = 256,
        metrics: RuntimeMetrics | None = None,
    ) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        super().__init__(enable_direct_mode=True)
        self._generator = generator
        self._max_tokens = max_tokens
        self._runtime_metrics = metrics

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction is FrameDirection.DOWNSTREAM and isinstance(
            frame, SemanticTurnFrame
        ):
            prompt = (
                "You are Simo, a concise realtime voice agent.\n\n"
                f"{frame.prompt}\n\n"
                f"Current user: {frame.user_text}"
            )
            metrics = self._runtime_metrics
            token = metrics.start_stage("text_inference") if metrics else None
            try:
                response = await self._generator.generate(
                    prompt,
                    max_tokens=self._max_tokens,
                )
            except Exception as error:
                if token:
                    metrics.finish_stage(token, error=True)
                await self.push_frame(
                    ErrorFrame(
                        error=f"local text inference failed: {error}", exception=error
                    ),
                    direction,
                )
                return
            if token:
                metrics.finish_stage(token)
            await self.push_frame(LLMFullResponseStartFrame(), direction)
            await self.push_frame(LLMTextFrame(text=response), direction)
            await self.push_frame(LLMFullResponseEndFrame(), direction)
            return
        await self.push_frame(frame, direction)
