from __future__ import annotations

import io
import json
import unittest
import wave
from unittest.mock import MagicMock, patch

from simo.breeze import verify_preview_site
from simo.config import RuntimeConfig


class PreviewProbeTests(unittest.TestCase):
    def probe(
        self,
        *,
        stream_rate: str = "24000",
        wav_rate: int = 24000,
        fingerprints: tuple[str | None, str | None, str | None] = ("a" * 64, "a" * 64, "a" * 64),
        final_fingerprint: str = "a" * 64,
    ) -> dict[str, object]:
        listing = json.dumps(
            {"presets": [{"id": "voice", "instruction": "test", "cached": False}]}
        ).encode()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(wav_rate)
            audio.writeframes(b"\x00\x00\x01\x00")

        def reply(
            body: bytes,
            rate: str = "24000",
            cache: str = "MISS",
            fingerprint: str | None = "a" * 64,
        ) -> MagicMock:
            result = MagicMock()
            result.status = 200
            headers = {
                "X-Sample-Rate": rate,
                "X-Sample-Format": "s16le",
                "X-Simo-Cache": cache,
                "X-Simo-Runtime-Fingerprint": fingerprint,
            }
            result.getheader = MagicMock(side_effect=headers.get)
            result.read1 = MagicMock(return_value=b"\x00\x00")
            result.read = MagicMock(return_value=body)
            return result

        replies = [
            reply(listing),
            reply(b"", fingerprint=fingerprints[0]),
            reply(listing),
            reply(b"\x01\x00", stream_rate, fingerprint=fingerprints[1]),
            reply(buffer.getvalue(), cache="HIT", fingerprint=fingerprints[2]),
        ]
        connection = MagicMock()
        connection.sock = None
        connection.getresponse = MagicMock(side_effect=replies)
        runtime = {"status": "ready", "busy": False, "runtime_fingerprint": "a" * 64}
        with (
            patch("simo.breeze.http.client.HTTPSConnection", return_value=connection),
            patch(
                "simo.breeze.health",
                side_effect=[
                    runtime,
                    {**runtime, "busy": True},
                    runtime,
                    {**runtime, "runtime_fingerprint": final_fingerprint},
                ],
            ),
        ):
            return verify_preview_site(RuntimeConfig.from_environment({}), url="https://test.local")

    def test_rejects_later_stream_and_wav_metadata_despite_equal_bytes(self) -> None:
        for stream_rate, wav_rate, message in (
            ("48000", 24000, "PCM metadata"),
            ("24000", 16000, "WAV format"),
        ):
            with (
                self.subTest(stream_rate=stream_rate, wav_rate=wav_rate),
                self.assertRaisesRegex(RuntimeError, message),
            ):
                self.probe(stream_rate=stream_rate, wav_rate=wav_rate)

    def test_rejects_missing_or_mismatched_response_fingerprints(self) -> None:
        for index in range(3):
            for bad in (None, "b" * 64):
                values: list[str | None] = ["a" * 64] * 3
                values[index] = bad
                with (
                    self.subTest(response=index, fingerprint=bad),
                    self.assertRaisesRegex(RuntimeError, "fingerprint does not match"),
                ):
                    self.probe(fingerprints=(values[0], values[1], values[2]))

    def test_rejects_changed_sidecar_identity(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "runtime changed"):
            self.probe(final_fingerprint="b" * 64)

    def test_records_verified_response_runtime(self) -> None:
        report = self.probe()
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["expected_runtime_fingerprint"], "a" * 64)
        self.assertIs(report["response_runtime_verified"], True)
