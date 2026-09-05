from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from simo.config import BREEZE_TTS_MODEL, QWEN_TTS_MODEL, RuntimeConfig, TTSBackend
from simo.inference import BreezeHTTPSynthesizer
from simo.livekit_runtime import config_for_alias_profile
from simo.persistence import SimoStore


class _Response:
    status = 200

    def __init__(self) -> None:
        self.payload = b"\x01\x00\x02\x00\x03\x00"

    def getheader(self, name: str, default: str) -> str:
        return {"X-Sample-Rate": "24000", "X-Sample-Format": "s16le"}.get(name, default)

    def read(self, size: int) -> bytes:
        selected, self.payload = self.payload[:size], self.payload[size:]
        return selected

    def read1(self, size: int) -> bytes:
        return self.read(size)


class _Connection:
    sock = None

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.body = b""

    def request(self, method: str, path: str, *, body: bytes, headers: object) -> None:
        del method, path, headers
        self.body = body

    def connect(self) -> None:
        pass

    def getresponse(self) -> _Response:
        return _Response()

    def close(self) -> None:
        pass


class BreezeTests(unittest.IsolatedAsyncioTestCase):
    async def test_loopback_client_streams_aligned_pcm_and_voice_controls(self) -> None:
        connection = _Connection()
        with patch("simo.inference.http.client.HTTPConnection", return_value=connection):
            synth = BreezeHTTPSynthesizer(
                "http://127.0.0.1:7860/v1/audio/speech",
                instruction="Warm and calm",
                cfg_scale=4,
                seed=7,
                read_bytes=3,
            )
            chunks = [chunk async for chunk in synth.synthesize("Hello")]

        self.assertEqual(b"\x01\x00\x02\x00\x03\x00", b"".join(chunk.pcm_s16le for chunk in chunks))
        self.assertTrue(all(chunk.sample_rate == 24_000 for chunk in chunks))
        self.assertIn(b"instruction=Warm+and+calm", connection.body)
        self.assertIn(b"seed=7", connection.body)

    async def test_alias_profiles_select_breeze_or_legacy_qwen_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SimoStore(Path(directory) / "data")
            breeze_alias = store.create_alias("Breeze")
            qwen_alias = store.create_alias(
                "Qwen",
                runtime_profile={
                    "schema": "simo.runtime-profile.v1",
                    "models": {},
                    "voice": "Aiden",
                },
            )
            config = RuntimeConfig.from_environment(
                {"SIMO_MODELS_DIR": str(Path(directory) / "models")}
            )

            breeze = config_for_alias_profile(store, breeze_alias.alias_id, config)
            qwen = config_for_alias_profile(store, qwen_alias.alias_id, config)
            rollback_config = RuntimeConfig.from_environment(
                {
                    "SIMO_MODELS_DIR": str(Path(directory) / "models"),
                    "SIMO_TTS_BACKEND": "qwen",
                }
            )
            rollback = config_for_alias_profile(store, breeze_alias.alias_id, rollback_config)

        self.assertEqual(TTSBackend.BREEZE, breeze.tts_backend)
        self.assertEqual(BREEZE_TTS_MODEL, breeze.tts.model_id)
        self.assertEqual(TTSBackend.QWEN, qwen.tts_backend)
        self.assertEqual(QWEN_TTS_MODEL, qwen.tts.model_id)
        self.assertEqual(TTSBackend.QWEN, rollback.tts_backend)
        self.assertEqual(QWEN_TTS_MODEL, rollback.tts.model_id)


if __name__ == "__main__":
    unittest.main()
