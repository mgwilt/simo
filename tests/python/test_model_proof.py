from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np

os.environ.setdefault(
    "NLTK_DATA",
    str(Path(__file__).resolve().parents[1] / "fixtures/nltk_data"),
)

from simo.config import RunMode, RuntimeConfig
from simo.inference import AudioChunk
from simo.model_proof import prove_models, resample_pcm_s16le


class FakeGenerator:
    async def generate(self, prompt: str, *, max_tokens: int) -> str:
        return "SIMO TEXT READY"


class FakeSynthesizer:
    async def synthesize(self, text: str):
        yield AudioChunk(b"\x00\x00" * 24_000, 24_000)


class FakeRecognizer:
    async def transcribe(self, pcm_s16le: bytes, sample_rate: int) -> str:
        return "The blue door is open."


class ModelProofTests(unittest.TestCase):
    def test_model_proof_executes_all_contracts_and_writes_wav(self) -> None:
        config = RuntimeConfig.from_environment({}, mode=RunMode.LIVE)
        with tempfile.TemporaryDirectory() as directory:
            vad = {
                "speech_utterances": 1,
                "playback_echo_turns": 0,
                "playback_suppressed_chunks": 50,
                "confidence": {"frames": 50, "mean_confidence": 0.5},
            }
            with patch(
                "simo.model_proof.prove_synthetic_vad",
                new=AsyncMock(return_value=vad),
            ):
                result = asyncio.run(
                    prove_models(
                        config,
                        Path(directory),
                        generator=FakeGenerator(),
                        synthesizer=FakeSynthesizer(),
                        recognizer=FakeRecognizer(),
                    )
                )
            path = Path(result["artifact"])
            self.assertTrue(path.is_file())
            with wave.open(str(path), "rb") as artifact:
                self.assertEqual(1, artifact.getnchannels())
                self.assertEqual(2, artifact.getsampwidth())
                self.assertEqual(24_000, artifact.getframerate())
            self.assertEqual("SIMO TEXT READY", result["text"]["response"])
            self.assertEqual("The blue door is open.", result["stt"]["transcript"])
            self.assertEqual(vad, result["vad"])
            self.assertEqual(1, result["pipeline"]["context_injections"])
            self.assertGreaterEqual(result["pipeline"]["audio_frames"], 1)
            self.assertGreater(result["pipeline"]["tts_audio_bytes"], 0)

    def test_resample_pcm_preserves_duration_and_bounds(self) -> None:
        samples = np.array([-32768, 0, 32767] * 8_000, dtype="<i2")
        result = resample_pcm_s16le(samples.tobytes(), 24_000, 16_000)
        converted = np.frombuffer(result, dtype="<i2")
        self.assertEqual(16_000, len(converted))
        self.assertGreaterEqual(int(converted.min()), -32768)
        self.assertLessEqual(int(converted.max()), 32767)

        with self.assertRaisesRegex(ValueError, "non-empty"):
            resample_pcm_s16le(b"", 24_000, 16_000)


if __name__ == "__main__":
    unittest.main()
