"""Local PCM utterance segmentation and Pipecat interruption signaling."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Protocol

import numpy as np
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADState
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    InterruptionFrame,
    OutputAudioRawFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.local.audio import (
    LocalAudioTransport,
    LocalAudioTransportParams,
)

from simo.adapters.pipecat.inference import PCMUtteranceFrame
from simo.operations import RuntimeMetrics


class ManagedLocalAudioTransport(LocalAudioTransport):
    """Add explicit PortAudio/executor release to Pipecat's local transport."""

    def __init__(self, params: LocalAudioTransportParams) -> None:
        super().__init__(params)
        self._simo_closed = False

    async def close(self) -> None:
        if self._simo_closed:
            return
        if self._input is not None:
            await self._input.cleanup()
        if self._output is not None:
            await self._output.cleanup()
            self._output._executor.shutdown(wait=True, cancel_futures=True)
        self._pyaudio.terminate()
        self._simo_closed = True


class VoiceActivityAnalyzer(Protocol):
    def set_sample_rate(self, sample_rate: int) -> None: ...

    async def analyze_audio(self, buffer: bytes) -> VADState: ...

    async def cleanup(self) -> None: ...


class ObservedSileroVADAnalyzer(SileroVADAnalyzer):
    """Record privacy-safe neural confidence aggregates for live diagnostics."""

    def __init__(self, *, runtime_metrics: RuntimeMetrics, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._runtime_metrics = runtime_metrics

    def voice_confidence(self, buffer: bytes) -> float:
        confidence = float(np.asarray(super().voice_confidence(buffer)).item())
        self._runtime_metrics.record_vad_confidence(confidence)
        return confidence


class SileroUtteranceProcessor(FrameProcessor):
    """Use semantic VAD states to build bounded utterance frames."""

    def __init__(
        self,
        analyzer: VoiceActivityAnalyzer,
        *,
        pre_roll_ms: int = 200,
        max_utterance_s: float = 30.0,
        user_id: str = "local-user",
        runtime_metrics: RuntimeMetrics | None = None,
    ) -> None:
        if pre_roll_ms <= 0 or max_utterance_s <= 0:
            raise ValueError("utterance timing bounds must be positive")
        super().__init__(enable_direct_mode=True)
        self._analyzer = analyzer
        self._pre_roll_ms = pre_roll_ms
        self._max_utterance_s = max_utterance_s
        self._user_id = user_id
        self._runtime_metrics = runtime_metrics
        self._pre_roll: deque[bytes] = deque()
        self._pre_roll_duration_ms = 0.0
        self._utterance = bytearray()
        self._sample_rate = 0
        self._speaking = False

    async def cleanup(self) -> None:
        await super().cleanup()
        await self._analyzer.cleanup()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction is not FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, InputAudioRawFrame):
            await self._process_audio(frame, direction)
            return
        if isinstance(frame, EndFrame):
            await self._finish_utterance(direction)
        elif isinstance(frame, CancelFrame):
            self._reset()
        await self.push_frame(frame, direction)

    async def _process_audio(
        self,
        frame: InputAudioRawFrame,
        direction: FrameDirection,
    ) -> None:
        if frame.num_channels != 1 or frame.sample_rate <= 0:
            raise ValueError("local input must be positive-rate mono PCM")
        if not frame.audio or len(frame.audio) % 2:
            raise ValueError("local input must be non-empty 16-bit PCM")
        if self._runtime_metrics is not None:
            self._runtime_metrics.record_audio_input_chunk()
        if self._sample_rate not in (0, frame.sample_rate):
            raise ValueError("local input sample rate changed during an utterance")
        if self._sample_rate == 0:
            self._analyzer.set_sample_rate(frame.sample_rate)
        self._sample_rate = frame.sample_rate
        duration_ms = frame.num_frames / frame.sample_rate * 1_000
        vad_state = await self._analyzer.analyze_audio(frame.audio)

        if not self._speaking:
            self._append_pre_roll(frame.audio, duration_ms)
            if vad_state is VADState.SPEAKING:
                self._speaking = True
                self._utterance.extend(b"".join(self._pre_roll))
                self._pre_roll.clear()
                self._pre_roll_duration_ms = 0.0
                await self.push_frame(UserStartedSpeakingFrame(), direction)
                await self.push_frame(InterruptionFrame(), direction)
                if self._runtime_metrics is not None:
                    self._runtime_metrics.record_user_speech_start(
                        interruption_signaled=True
                    )
            return

        self._utterance.extend(frame.audio)
        utterance_s = len(self._utterance) / (self._sample_rate * 2)
        if vad_state is VADState.QUIET or utterance_s >= self._max_utterance_s:
            await self._finish_utterance(direction)

    def _append_pre_roll(self, audio: bytes, duration_ms: float) -> None:
        self._pre_roll.append(audio)
        self._pre_roll_duration_ms += duration_ms
        while self._pre_roll and self._pre_roll_duration_ms > self._pre_roll_ms:
            removed = self._pre_roll.popleft()
            self._pre_roll_duration_ms -= len(removed) / (self._sample_rate * 2) * 1_000

    async def _finish_utterance(self, direction: FrameDirection) -> None:
        if not self._speaking or not self._utterance:
            self._reset()
            return
        audio = bytes(self._utterance)
        sample_rate = self._sample_rate
        await self.push_frame(UserStoppedSpeakingFrame(), direction)
        await self.push_frame(_acknowledgement_tone(), direction)
        await self.push_frame(
            PCMUtteranceFrame(
                audio=audio,
                sample_rate=sample_rate,
                user_id=self._user_id,
                timestamp=datetime.now(UTC).isoformat(),
            ),
            direction,
        )
        self._reset()

    def _reset(self) -> None:
        self._pre_roll.clear()
        self._pre_roll_duration_ms = 0.0
        self._utterance.clear()
        self._sample_rate = 0
        self._speaking = False


def _acknowledgement_tone() -> OutputAudioRawFrame:
    sample_rate = 24_000
    positions = np.arange(round(sample_rate * 0.07), dtype=np.float32) / sample_rate
    wave = np.sin(2 * np.pi * 1_040 * positions) * 0.12
    return OutputAudioRawFrame(
        audio=(wave * 32767).astype("<i2").tobytes(),
        sample_rate=sample_rate,
        num_channels=1,
    )
