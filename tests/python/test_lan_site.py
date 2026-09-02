from __future__ import annotations

import asyncio
import tempfile
import unittest
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, Request
from simo.config import RuntimeConfig
from simo.inference import AudioChunk
from simo.lan_site import LanSiteSettings, _BrowserSessionIssuer, _caddyfile
from simo.livekit_room import LiveKitRoomConfig


class LanSiteTests(unittest.TestCase):
    def test_settings_require_existing_tls_and_non_loopback_ip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            certificate = root / "cert.pem"
            key = root / "key.pem"
            certificate.touch()
            key.touch()
            settings = LanSiteSettings(
                "alias-1",
                "simo.local",
                certificate,
                key,
                "192.168.1.10",
            )

            self.assertEqual("https://simo.local:8443", settings.site_url)
            with self.assertRaisesRegex(ValueError, "non-loopback"):
                LanSiteSettings("alias-1", "simo.local", certificate, key, "127.0.0.1")

    def test_caddy_routes_only_site_api_and_livekit_signaling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            certificate = root / "cert.pem"
            key = root / "key.pem"
            web = root / "dist"
            certificate.touch()
            key.touch()
            web.mkdir()
            settings = LanSiteSettings(
                "alias-1",
                "simo.local",
                certificate,
                key,
                "192.168.1.10",
            )

            rendered = _caddyfile(settings, 9000, 7880, web)

        self.assertIn("handle /api/*", rendered)
        self.assertIn("handle /rtc*", rendered)
        self.assertIn("reverse_proxy 127.0.0.1:9000", rendered)
        self.assertNotIn("api_secret", rendered)

    def test_session_retries_follow_the_browser_host_without_expanding_identity(self) -> None:
        room = LiveKitRoomConfig(
            "ws://127.0.0.1:7880",
            "key",
            "secret-long-enough-for-a-token-and-sha256",
            "room",
            "simo-browser",
            "LAN browser",
            frozenset({"simo-alias"}),
        )
        issuer = _BrowserSessionIssuer(
            room,
            RuntimeConfig.from_environment({}),
            alias_name="Ada",
            allowed_hosts=frozenset({"simo.local", "192.168.1.10"}),
            https_port=8443,
        )
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/session",
                "headers": [(b"host", b"192.168.1.10:8443")],
            }
        )

        first = asyncio.run(issuer.issue(request))
        retry = asyncio.run(issuer.issue(request))

        self.assertEqual("wss://192.168.1.10:8443", first["serverUrl"])
        self.assertEqual("wss://192.168.1.10:8443", retry["serverUrl"])
        self.assertTrue(first["participantToken"])
        with self.assertRaises(HTTPException):
            asyncio.run(
                issuer.issue(
                    Request(
                        {
                            "type": "http",
                            "method": "POST",
                            "path": "/api/session",
                            "headers": [(b"host", b"example.com:8443")],
                        }
                    )
                )
            )

    def test_voice_preview_is_curated_wav_and_cached(self) -> None:
        class _Synthesizer:
            calls = 0

            def __init__(self, *args: object, **kwargs: object) -> None:
                del args, kwargs

            async def synthesize(self, text: str) -> AsyncIterator[AudioChunk]:
                self.assert_text = text
                self.__class__.calls += 1
                yield AudioChunk(b"\x01\x00\x02\x00", 24_000)

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            config = replace(RuntimeConfig.from_environment({}), repository=repository)
            room = LiveKitRoomConfig(
                "ws://127.0.0.1:7880",
                "key",
                "secret-long-enough-for-a-token-and-sha256",
                "room",
                "simo-browser",
                "LAN browser",
                frozenset({"simo-alias"}),
            )
            issuer = _BrowserSessionIssuer(
                room,
                config,
                alias_name="Ada",
                allowed_hosts=frozenset({"simo.local"}),
                https_port=8443,
            )
            with patch("simo.lan_site.BreezeHTTPSynthesizer", _Synthesizer):
                first = asyncio.run(issuer.preview("warm-companion"))
                cached = asyncio.run(issuer.preview("warm-companion"))

        self.assertTrue(bytes(first.body).startswith(b"RIFF"))
        self.assertEqual("MISS", first.headers["x-simo-cache"])
        self.assertEqual("HIT", cached.headers["x-simo-cache"])
        self.assertEqual(1, _Synthesizer.calls)


if __name__ == "__main__":
    unittest.main()
