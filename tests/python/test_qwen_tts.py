from __future__ import annotations

import os
import threading
import unittest
from collections.abc import AsyncGenerator
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import numpy as np

os.environ.setdefault(
    "NLTK_DATA",
    str(Path(__file__).resolve().parents[1] / "fixtures/nltk_data"),
)

from pipecat.frames.frames import ErrorFrame, TTSAudioRawFrame
from simo.adapters.pipecat.qwen_tts import QwenMLXTTSService
from simo.inference import AudioChunk, MLXAudioSynthesizer
from simo.operations import RuntimeMetrics


class FakeQwenModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.closed = threading.Event()

    def generate(self, **kwargs: object):
        self.calls.append(kwargs)
        try:
            yield SimpleNamespace(
                audio=np.array([-2.0, -1.0, 0.0, 0.5, 1.0, 2.0]),
                sample_rate=24_000,
            )
            yield SimpleNamespace(audio=np.array([0.25]), sample_rate=24_000)
        finally:
            self.closed.set()


class FailingSynthesizer:
    async def synthesize(self, text: str):
        if text == "invalid":
            yield AudioChunk(b"\x00", 24_000)
            return
        if text == "rate":
            yield AudioChunk(b"\x00\x00", 0)
            return
        raise RuntimeError("model failed")
        yield  # pragma: no cover


class QwenTTSBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_mlx_audio_is_lazy_streaming_and_converts_pcm(self) -> None:
        model = FakeQwenModel()
        loads: list[str] = []
        synthesizer = MLXAudioSynthesizer(
            Path("/models/qwen-tts"),
            voice="Aiden",
            streaming_interval_s=0.32,
            max_tokens=99,
            model_loader=lambda path: loads.append(path) or model,
        )

        chunks = [chunk async for chunk in synthesizer.synthesize("hello")]

        self.assertEqual(["/models/qwen-tts"], loads)
        self.assertEqual(2, len(chunks))
        self.assertEqual(24_000, chunks[0].sample_rate)
        self.assertEqual(
            [-32767, -32767, 0, 16383, 32767, 32767],
            np.frombuffer(chunks[0].pcm_s16le, dtype="<i2").tolist(),
        )
        self.assertEqual("hello", model.calls[0]["text"])
        self.assertEqual("Aiden", model.calls[0]["voice"])
        self.assertTrue(model.calls[0]["stream"])
        self.assertEqual(0.32, model.calls[0]["streaming_interval"])
        self.assertEqual(99, model.calls[0]["max_tokens"])
        self.assertFalse(model.calls[0]["verbose"])

    async def test_consumer_close_cancels_between_generated_chunks(self) -> None:
        model = FakeQwenModel()
        synthesizer = MLXAudioSynthesizer(
            Path("/models/qwen-tts"),
            queue_capacity=1,
            model_loader=lambda path: model,
        )
        stream = cast(AsyncGenerator[AudioChunk, None], synthesizer.synthesize("interrupt me"))

        first = await anext(stream)
        self.assertTrue(first.pcm_s16le)
        await stream.aclose()

        self.assertTrue(model.closed.wait(timeout=1.0))

    async def test_pipecat_service_emits_contextual_pcm_and_bounds_errors(self) -> None:
        model = FakeQwenModel()
        metrics = RuntimeMetrics()
        service = QwenMLXTTSService(
            MLXAudioSynthesizer(
                Path("/models/qwen-tts"),
                model_loader=lambda path: model,
            ),
            metrics=metrics,
        )

        frames = [frame async for frame in service.run_tts("hello", "turn-1")]

        self.assertEqual(2, len(frames))
        audio_frames = [frame for frame in frames if isinstance(frame, TTSAudioRawFrame)]
        self.assertEqual(len(frames), len(audio_frames))
        self.assertTrue(all(frame.context_id == "turn-1" for frame in audio_frames))
        self.assertTrue(all(frame.sample_rate == 24_000 for frame in audio_frames))
        self.assertTrue(all(frame.num_channels == 1 for frame in audio_frames))
        tts_metrics = metrics.snapshot()["stages"]["tts"]
        self.assertEqual(1, tts_metrics["calls"])
        self.assertIsNotNone(tts_metrics["first_output_ms"])

        for text, message in (
            ("invalid", "invalid 16-bit PCM"),
            ("rate", "invalid sample rate"),
            ("fail", "model failed"),
        ):
            failed = QwenMLXTTSService(FailingSynthesizer())
            error_frames = [frame async for frame in failed.run_tts(text, "turn-error")]
            self.assertEqual(1, len(error_frames))
            errors = [frame for frame in error_frames if isinstance(frame, ErrorFrame)]
            self.assertEqual(1, len(errors))
            self.assertIn(message, errors[0].error)


if __name__ == "__main__":
    unittest.main()
