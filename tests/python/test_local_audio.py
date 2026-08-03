from __future__ import annotations

import os
import unittest
from array import array
from math import fsum, pi, sin, sqrt
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np

os.environ.setdefault(
    "NLTK_DATA",
    str(Path(__file__).resolve().parents[1] / "fixtures/nltk_data"),
)

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADState
from pipecat.frames.frames import (
    CancelFrame,
    ErrorFrame,
    InputAudioRawFrame,
    InterruptionFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from simo.adapters.pipecat.inference import PCMUtteranceFrame
from simo.adapters.pipecat.local_audio import (
    ManagedLocalAudioTransport,
    ObservedSileroVADAnalyzer,
    PlaybackState,
    PlaybackStateProcessor,
    SileroUtteranceProcessor,
    condition_pcm_for_silero,
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
    async def test_conditioning_removes_dc_and_applies_bounded_gain(self) -> None:
        samples = array(
            "h",
            (round(400 + sin(2 * pi * 440 * index / 16_000) * 300) for index in range(512)),
        )

        conditioned = condition_pcm_for_silero(samples.tobytes())

        values = array("h")
        values.frombytes(conditioned)
        mean = fsum(values) / len(values)
        rms = sqrt(fsum(value * value for value in values) / len(values)) / 32768.0
        self.assertLess(abs(mean), 1.0)
        self.assertAlmostEqual(
            0.05,
            rms,
            places=3,
        )

    async def test_observed_silero_extracts_array_confidence(self) -> None:
        metrics = RuntimeMetrics()
        analyzer = object.__new__(ObservedSileroVADAnalyzer)
        analyzer._runtime_metrics = metrics

        with patch.object(
            SileroVADAnalyzer,
            "voice_confidence",
            return_value=np.asarray([0.42], dtype=np.float32),
        ):
            confidence = analyzer.voice_confidence(b"\x00\x00" * 512)

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
        self.assertIsInstance(frames[3], PCMUtteranceFrame)
        utterance = frames[3]
        self.assertEqual(16_000, utterance.sample_rate)  # type: ignore[union-attr]
        self.assertEqual(5 * 640, len(utterance.audio))  # type: ignore[union-attr]
        self.assertEqual([16_000], analyzer.sample_rates)
        self.assertEqual(
            {
                "input_chunks": 5,
                "playback_suppressed_chunks": 0,
                "utterances_started": 1,
                "interruption_signals": 1,
            },
            metrics.snapshot()["audio_activity"],
        )

    async def test_cancel_discards_partial_utterance(self) -> None:
        processor = SileroUtteranceProcessor(FakeAnalyzer([VADState.SPEAKING, VADState.QUIET]))
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
        processor = SileroUtteranceProcessor(FakeAnalyzer([VADState.SPEAKING, VADState.SPEAKING]))
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

    async def test_vad_failure_emits_error_and_increments_metrics(self) -> None:
        class FailingAnalyzer(FakeAnalyzer):
            async def analyze_audio(self, buffer: bytes) -> VADState:
                raise RuntimeError("failed")

        metrics = RuntimeMetrics()
        processor = SileroUtteranceProcessor(
            FailingAnalyzer([]),
            runtime_metrics=metrics,
        )
        frames: list[object] = []

        async def collect(frame: object, direction: FrameDirection) -> None:
            frames.append(frame)

        processor.push_frame = collect  # type: ignore[method-assign]
        await processor.process_frame(audio_frame(3_000), FrameDirection.DOWNSTREAM)

        self.assertIsInstance(frames[0], ErrorFrame)
        self.assertEqual(1, metrics.snapshot()["errors_total"])

    async def test_playback_state_suppresses_microphone_turns(self) -> None:
        now = [10.0]
        state = PlaybackState(clock=lambda: now[0])
        tracker = PlaybackStateProcessor(state)
        with patch.object(tracker, "push_frame", new=AsyncMock()):
            await tracker.process_frame(TTSStartedFrame(), FrameDirection.DOWNSTREAM)
            output = TTSAudioRawFrame(
                audio=b"\x00\x00" * 2_400,
                sample_rate=24_000,
                num_channels=1,
            )
            await tracker.process_frame(output, FrameDirection.DOWNSTREAM)
            await tracker.process_frame(output, FrameDirection.DOWNSTREAM)
            self.assertTrue(state.active)

        metrics = RuntimeMetrics()
        segmenter = SileroUtteranceProcessor(
            FakeAnalyzer([VADState.SPEAKING]),
            runtime_metrics=metrics,
            playback_state=state,
        )
        with patch.object(segmenter, "push_frame", new=AsyncMock()):
            await segmenter.process_frame(audio_frame(3_000), FrameDirection.DOWNSTREAM)

        self.assertEqual(0, metrics.snapshot()["audio_activity"]["utterances_started"])
        self.assertEqual(
            1,
            metrics.snapshot()["audio_activity"]["playback_suppressed_chunks"],
        )
        with patch.object(tracker, "push_frame", new=AsyncMock()):
            await tracker.process_frame(TTSStoppedFrame(), FrameDirection.DOWNSTREAM)
        self.assertTrue(state.active)
        now[0] += 0.36
        self.assertFalse(state.active)

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
