from __future__ import annotations

import tempfile
import unittest
import wave
from dataclasses import replace
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import httpx
from simo.cli import main
from simo.config import RuntimeConfig
from simo.lan_site import VOICE_PREVIEW_PRESETS
from simo.preview_site import PreviewSiteSettings, create_preview_site, validate_assets


class PreviewSiteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        (self.assets / "preview.html").write_text("<h1>Experimental preview</h1>")
        self.cert, self.key = self.root / "cert.pem", self.root / "key.pem"
        self.cert.touch()
        self.key.write_text("synthetic-private-key")
        self.settings = PreviewSiteSettings("192.168.1.10", self.cert, self.key, self.assets)
        self.config = replace(
            RuntimeConfig.from_environment({}),
            repository=self.root,
            tts_endpoint="http://127.0.0.1:7861/v1/audio/speech",
        )
        self.identity: dict[str, object] = {
            "status": "ready",
            "sample_rate": 24_000,
            "experimental_recipe": "mlx-int8-v1",
            "performance_mode": "experimental",
            "release_accepted": False,
            "runtime_fingerprint": "a" * 64,
        }

    async def test_only_preview_routes_and_static_files_are_exposed(self) -> None:
        with (
            patch("simo.preview_site.breeze_health", return_value=self.identity),
            patch(
                "simo.lan_site.LiveKitAliasRuntime",
                side_effect=AssertionError("conversation created"),
            ),
            patch("simo.lan_site.SimoStore", side_effect=AssertionError("store created")),
        ):
            service = create_preview_site(self.config, self.settings)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=service.app), base_url=self.settings.site_url
            ) as client:
                self.assertEqual((await client.get("/")).status_code, 200)
                health = await client.get("/api/health")
                self.assertEqual(health.status_code, 200)
                self.assertEqual(health.json()["playback_policy"], "complete-clip")
                listing = await client.get("/api/previews")
                self.assertEqual(listing.status_code, 200)
                payload = cast(dict[str, object], listing.json())
                self.assertEqual(len(cast(list[object], payload["presets"])), 3)
                for path in (
                    "/api/session",
                    "/api/conversations",
                    "/rtc",
                    "/openapi.json",
                    "/key.pem",
                    "/src/preview-only.ts",
                    "/%2e%2e/key.pem",
                ):
                    self.assertEqual((await client.get(path)).status_code, 404)
                    self.assertIn((await client.post(path)).status_code, (404, 405))

    async def test_host_origin_and_runtime_are_checked_without_cors(self) -> None:
        with patch("simo.preview_site.breeze_health", return_value=self.identity):
            service = create_preview_site(self.config, self.settings)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=service.app), base_url=self.settings.site_url
            ) as client:
                self.assertEqual(
                    (
                        await client.get("/api/health", headers={"Host": "evil.test:8444"})
                    ).status_code,
                    400,
                )
                forbidden = await client.post(
                    "/api/previews/warm-companion", headers={"Origin": "https://evil.test"}
                )
                self.assertEqual(forbidden.status_code, 403)
                self.assertNotIn("access-control-allow-origin", forbidden.headers)
                self.assertEqual(
                    (
                        await client.get("/api/health", headers={"Origin": self.settings.site_url})
                    ).status_code,
                    200,
                )
                self.identity["performance_mode"] = "quality"
                self.assertEqual((await client.get("/api/previews")).status_code, 503)

    def test_settings_and_asset_allowlist_fail_closed(self) -> None:
        for address in ("0.0.0.0", "127.0.0.1", "8.8.8.8", "224.0.0.1"):  # noqa: S104 - rejected addresses, no binding
            with self.assertRaises(ValueError):
                replace(self.settings, node_ip=address)
        with self.assertRaises(ValueError):
            replace(self.settings, https_port=8443)
        for fingerprint in ("", "a" * 63, "g" * 64):
            with self.assertRaises(ValueError):
                replace(self.settings, streaming_runtime=fingerprint)
        with self.assertRaises(ValueError):
            create_preview_site(replace(self.config, tts_cfg_scale=1), self.settings)
        (self.assets / "key.pem").write_text("not-for-serving")
        with self.assertRaisesRegex(ValueError, "unexpected"):
            validate_assets(self.assets)

    async def test_streaming_opt_in_is_bound_to_exact_runtime_and_response_headers(self) -> None:
        settings = replace(self.settings, streaming_runtime="a" * 64)
        with patch("simo.preview_site.breeze_health", return_value=self.identity):
            service = create_preview_site(self.config, settings)
            preset = VOICE_PREVIEW_PRESETS[0]
            path = service._preview_path(preset, "a" * 64)
            path.parent.mkdir(parents=True)
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(24_000)
                output.writeframes(b"\x01\x00" * 128)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=service.app), base_url=settings.site_url
            ) as client:
                for route in ("/api/health", "/api/previews"):
                    response = await client.get(route)
                    self.assertEqual(response.json()["playback_policy"], "mlx-stream-v1")
                    self.assertEqual(response.json()["runtime_fingerprint"], "a" * 64)
                for suffix in ("", "/stream"):
                    response = await client.post(f"/api/previews/{preset.preset_id}{suffix}")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.headers["X-Simo-Playback-Policy"], "mlx-stream-v1")
                    self.assertEqual(response.headers["X-Simo-Runtime-Fingerprint"], "a" * 64)
                self.identity["runtime_fingerprint"] = "b" * 64
                self.assertEqual((await client.get("/api/previews")).status_code, 503)
                self.assertEqual(
                    (await client.post(f"/api/previews/{preset.preset_id}/stream")).status_code,
                    503,
                )

    def test_cli_bypasses_conversation_and_full_runtime_preflight(self) -> None:
        # Run a separate loop from this synchronous unittest method.
        with (
            patch("simo.cli.inspect_runtime", side_effect=AssertionError("full preflight")),
            patch("simo.preview_site.run_preview_site", new_callable=AsyncMock) as runner,
        ):
            result = main(
                [
                    "breeze",
                    "serve-preview",
                    "--node-ip",
                    "192.168.1.10",
                    "--cert",
                    str(self.cert),
                    "--key",
                    str(self.key),
                    "--assets",
                    str(self.assets),
                ]
            )
        self.assertEqual(result, 0)
        self.assertEqual(runner.await_count, 1)

    def test_results_never_overlap_assets_or_deck_even_with_dotdot(self) -> None:
        deck = self.root / "deck" / "deck.json"
        safe = self.root / "safe"
        safe.mkdir()
        for path in (
            self.assets / "results",
            safe / ".." / "assets" / "results",
            self.root,
            deck.parent / "results",
        ):
            with self.assertRaisesRegex(ValueError, "separate|own directory"):
                replace(self.settings, listening_deck=deck, listening_results=path)
        self.assertFalse((self.assets / "results").exists())
        replace(self.settings, listening_deck=deck, listening_results=self.root / "results")
        with self.assertRaisesRegex(ValueError, "require a listening deck"):
            replace(self.settings, listening_results=self.root / "results")
