from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

os.environ.setdefault(
    "NLTK_DATA",
    str(Path(__file__).resolve().parents[1] / "fixtures/nltk_data"),
)

from pipecat.audio.vad.vad_analyzer import VADState
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import (
    CancelFrame,
    InputAudioRawFrame,
    InterruptionFrame,
    OutputAudioRawFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from simo.adapters.pipecat.inference import PCMUtteranceFrame
from simo.adapters.pipecat.local_audio import (
    ManagedLocalAudioTransport,
    ObservedSileroVADAnalyzer,
    SileroUtteranceProcessor,
)
from simo.operations import RuntimeMetrics


def audio_frame(sample: int, *, sample_rate: int = 16_000) -> InputAudioRawFrame:
    return InputAudioRawFrame(
        audio=int(sample).to_bytes(2, "little", signed=True) * 320,
        sample_rate=sample_rate,
        num_channels=1,
    )


class FakeAnalyzer:
    def __init__(self, states: list[VADState]) -> None:
        self.states = iter(states)
        self.sample_rates: list[int] = []
        self.cleaned = False

    def set_sample_rate(self, sample_rate: int) -> None:
        self.sample_rates.append(sample_rate)

    async def analyze_audio(self, buffer: bytes) -> VADState:
        return next(self.states, VADState.QUIET)

    async def cleanup(self) -> None:
        self.cleaned = True


class SileroUtteranceTests(unittest.IsolatedAsyncioTestCase):
    async def test_observed_silero_extracts_array_confidence(self) -> None:
        metrics = RuntimeMetrics()
        analyzer = object.__new__(ObservedSileroVADAnalyzer)
        analyzer._runtime_metrics = metrics

        with patch.object(
            SileroVADAnalyzer,
            "voice_confidence",
            return_value=np.asarray([0.42], dtype=np.float32),
        ):
            confidence = analyzer.voice_confidence(b"pcm")

        self.assertAlmostEqual(0.42, confidence, places=5)
        self.assertEqual(1, metrics.snapshot()["vad_analysis"]["frames"])

    async def test_segments_pcm_and_emits_interruption_at_speech_start(self) -> None:
        metrics = RuntimeMetrics()
        analyzer = FakeAnalyzer(
            [
                VADState.STARTING,
                VADState.SPEAKING,
                VADState.SPEAKING,
                VADState.STOPPING,
                VADState.QUIET,
            ]
        )
        processor = SileroUtteranceProcessor(
            analyzer,
            pre_roll_ms=200,
            runtime_metrics=metrics,
        )
        frames: list[object] = []

        async def collect(frame: object, direction: FrameDirection) -> None:
            frames.append(frame)

        processor.push_frame = collect  # type: ignore[method-assign]
        for _ in range(5):
            await processor.process_frame(audio_frame(3_000), FrameDirection.DOWNSTREAM)

        self.assertIsInstance(frames[0], UserStartedSpeakingFrame)
        self.assertIsInstance(frames[1], InterruptionFrame)
        self.assertIsInstance(frames[2], UserStoppedSpeakingFrame)
        self.assertIsInstance(frames[3], OutputAudioRawFrame)
        self.assertEqual(24_000, frames[3].sample_rate)  # type: ignore[union-attr]
        self.assertIsInstance(frames[4], PCMUtteranceFrame)
        utterance = frames[4]
        self.assertEqual(16_000, utterance.sample_rate)  # type: ignore[union-attr]
        self.assertEqual(5 * 640, len(utterance.audio))  # type: ignore[union-attr]
        self.assertEqual([16_000], analyzer.sample_rates)
        self.assertEqual(
            {
                "input_chunks": 5,
                "utterances_started": 1,
                "interruption_signals": 1,
            },
            metrics.snapshot()["audio_activity"],
        )

    async def test_cancel_discards_partial_utterance(self) -> None:
        processor = SileroUtteranceProcessor(
            FakeAnalyzer([VADState.SPEAKING, VADState.QUIET])
        )
        frames: list[object] = []

        async def collect(frame: object, direction: FrameDirection) -> None:
            frames.append(frame)

        processor.push_frame = collect  # type: ignore[method-assign]
        await processor.process_frame(audio_frame(3_000), FrameDirection.DOWNSTREAM)
        await processor.process_frame(CancelFrame(), FrameDirection.DOWNSTREAM)
        for _ in range(3):
            await processor.process_frame(audio_frame(0), FrameDirection.DOWNSTREAM)

        self.assertFalse(any(isinstance(frame, PCMUtteranceFrame) for frame in frames))
        self.assertIsInstance(frames[-1], CancelFrame)

    async def test_rejects_non_mono_and_sample_rate_changes(self) -> None:
        processor = SileroUtteranceProcessor(
            FakeAnalyzer([VADState.SPEAKING, VADState.SPEAKING])
        )
        stereo = InputAudioRawFrame(b"\x00\x00" * 640, 16_000, 2)
        with self.assertRaisesRegex(ValueError, "mono"):
            await processor.process_frame(stereo, FrameDirection.DOWNSTREAM)

        await processor.process_frame(audio_frame(3_000), FrameDirection.DOWNSTREAM)
        with self.assertRaisesRegex(ValueError, "sample rate changed"):
            await processor.process_frame(
                audio_frame(3_000, sample_rate=24_000),
                FrameDirection.DOWNSTREAM,
            )

    async def test_cleanup_releases_vad_analyzer(self) -> None:
        analyzer = FakeAnalyzer([])
        processor = SileroUtteranceProcessor(analyzer)

        await processor.cleanup()

        self.assertTrue(analyzer.cleaned)

    async def test_managed_transport_releases_pyaudio_and_executor_once(self) -> None:
        calls: list[str] = []

        class Stream:
            async def cleanup(self) -> None:
                calls.append("stream")

        class Executor:
            def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
                calls.append(f"executor:{wait}:{cancel_futures}")

        class Output(Stream):
            _executor = Executor()

        class PyAudio:
            def terminate(self) -> None:
                calls.append("pyaudio")

        transport = object.__new__(ManagedLocalAudioTransport)
        transport._simo_closed = False
        transport._input = Stream()
        transport._output = Output()
        transport._pyaudio = PyAudio()

        await transport.close()
        await transport.close()

        self.assertEqual(
            ["stream", "stream", "executor:True:True", "pyaudio"],
            calls,
        )


if __name__ == "__main__":
    unittest.main()
