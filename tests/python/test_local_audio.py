from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault(
    "NLTK_DATA",
    str(Path(__file__).resolve().parents[1] / "fixtures/nltk_data"),
)

from pipecat.frames.frames import (
    CancelFrame,
    InputAudioRawFrame,
    InterruptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from simo.adapters.pipecat.inference import PCMUtteranceFrame
from simo.adapters.pipecat.local_audio import (
    EnergyUtteranceProcessor,
    ManagedLocalAudioTransport,
)
from simo.operations import RuntimeMetrics


def audio_frame(sample: int, *, sample_rate: int = 16_000) -> InputAudioRawFrame:
    return InputAudioRawFrame(
        audio=int(sample).to_bytes(2, "little", signed=True) * 320,
        sample_rate=sample_rate,
        num_channels=1,
    )


class EnergyUtteranceTests(unittest.IsolatedAsyncioTestCase):
    async def test_segments_pcm_and_emits_interruption_at_speech_start(self) -> None:
        metrics = RuntimeMetrics()
        processor = EnergyUtteranceProcessor(
            start_rms=0.02,
            start_ms=60,
            stop_ms=60,
            pre_roll_ms=200,
            runtime_metrics=metrics,
        )
        frames: list[object] = []

        async def collect(frame: object, direction: FrameDirection) -> None:
            frames.append(frame)

        processor.push_frame = collect  # type: ignore[method-assign]
        for _ in range(3):
            await processor.process_frame(audio_frame(3_000), FrameDirection.DOWNSTREAM)
        for _ in range(3):
            await processor.process_frame(audio_frame(0), FrameDirection.DOWNSTREAM)

        self.assertIsInstance(frames[0], UserStartedSpeakingFrame)
        self.assertIsInstance(frames[1], InterruptionFrame)
        self.assertIsInstance(frames[2], UserStoppedSpeakingFrame)
        self.assertIsInstance(frames[3], PCMUtteranceFrame)
        utterance = frames[3]
        self.assertEqual(16_000, utterance.sample_rate)  # type: ignore[union-attr]
        self.assertEqual(6 * 640, len(utterance.audio))  # type: ignore[union-attr]
        self.assertEqual(
            {"utterances_started": 1, "interruption_signals": 1},
            metrics.snapshot()["audio_activity"],
        )

    async def test_cancel_discards_partial_utterance(self) -> None:
        processor = EnergyUtteranceProcessor(start_ms=20, stop_ms=60)
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
        processor = EnergyUtteranceProcessor(start_ms=60)
        stereo = InputAudioRawFrame(b"\x00\x00" * 640, 16_000, 2)
        with self.assertRaisesRegex(ValueError, "mono"):
            await processor.process_frame(stereo, FrameDirection.DOWNSTREAM)

        await processor.process_frame(audio_frame(3_000), FrameDirection.DOWNSTREAM)
        with self.assertRaisesRegex(ValueError, "sample rate changed"):
            await processor.process_frame(
                audio_frame(3_000, sample_rate=24_000),
                FrameDirection.DOWNSTREAM,
            )

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
