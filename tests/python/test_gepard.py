from __future__ import annotations

import io
import json
import unittest
import wave
from unittest.mock import patch

from simo.gepard import (
    GEPARD_SAMPLE_RATE,
    GepardHttpClient,
    GepardRequest,
    decode_gepard_wav,
    iter_pcm_chunks,
)


def make_wav(*, sample_rate: int = GEPARD_SAMPLE_RATE, channels: int = 1) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x01\x00" * channels * 1_000)
    return output.getvalue()


class GepardBoundaryTests(unittest.TestCase):
    def test_request_uses_reference_server_contract(self) -> None:
        self.assertEqual(
            {"text": "hello", "reference": "voice.wav", "cfg_scale": 3.0},
            GepardRequest("hello", "voice.wav", 3.0).as_payload(),
        )

    def test_wav_validation_and_deterministic_chunks(self) -> None:
        audio = decode_gepard_wav(make_wav())
        chunks = list(iter_pcm_chunks(audio, chunk_duration_ms=20))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) % 2 == 0 for chunk in chunks))
        self.assertEqual(audio.data, b"".join(chunks))

    def test_http_client_posts_documented_endpoint_and_decodes_wav(self) -> None:
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return make_wav()

        with patch("simo.gepard.urlopen", return_value=Response()) as urlopen_mock:
            audio = GepardHttpClient("http://gepard.local", timeout_s=2).synthesize(
                GepardRequest("hello")
            )

        request = urlopen_mock.call_args.args[0]
        self.assertEqual("http://gepard.local/synthesize", request.full_url)
        self.assertEqual("POST", request.method)
        self.assertEqual({"text": "hello"}, json.loads(request.data))
        self.assertEqual(GEPARD_SAMPLE_RATE, audio.sample_rate)

    def test_rejects_wrong_sample_rate_and_channels(self) -> None:
        with self.assertRaisesRegex(ValueError, "22050"):
            decode_gepard_wav(make_wav(sample_rate=16_000))
        with self.assertRaisesRegex(ValueError, "mono"):
            decode_gepard_wav(make_wav(channels=2))


if __name__ == "__main__":
    unittest.main()
