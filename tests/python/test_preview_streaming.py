from __future__ import annotations

import asyncio
import tempfile
import unittest
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from typing import cast
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.responses import Response
from simo.config import RuntimeConfig
from simo.inference import AudioChunk
from simo.lan_site import VOICE_PREVIEW_PRESETS, _BrowserSessionIssuer
from simo.livekit_room import LiveKitRoomConfig
from starlette.requests import ClientDisconnect
from starlette.types import Message, Scope, Send


class PreviewStreamingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.directory.name)
        config = replace(RuntimeConfig.from_environment({}), repository=self.repository)
        room = LiveKitRoomConfig(
            "ws://127.0.0.1:7880",
            "key",
            "synthetic-test-secret-long-enough",
            "room",
            "simo-browser",
            "Browser",
            frozenset({"simo-alias"}),
        )
        self.issuer = _BrowserSessionIssuer(
            room, config, alias_name="Ada", allowed_hosts=frozenset({"simo.local"}), https_port=8443
        )
        self.ready = patch(
            "simo.lan_site.breeze_health",
            return_value={"status": "ready", "runtime_fingerprint": "test"},
        )
        self.ready.start()

    def tearDown(self) -> None:
        self.ready.stop()
        self.directory.cleanup()

    async def test_miss_streams_before_eof_and_hit_matches_pcm(self) -> None:
        proceed = asyncio.Event()
        first_sent = asyncio.Event()
        output: list[bytes] = []

        class Synthesizer:
            calls = 0

            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            async def synthesize(self, text: str) -> AsyncIterator[AudioChunk]:
                self.__class__.calls += 1
                yield AudioChunk(b"\x01\x00", 24_000)
                await proceed.wait()
                yield AudioChunk(b"\x02\x00", 24_000)

        async def send(message: Message) -> None:
            body = cast(object, message.get("body"))
            if isinstance(body, bytes) and body:
                output.append(body)
                first_sent.set()

        with patch("simo.lan_site.BreezeHTTPSynthesizer", Synthesizer):
            response = await self.issuer.preview_stream("warm-companion")
            task = asyncio.create_task(self._run(response, send))
            try:
                await asyncio.wait_for(first_sent.wait(), 1)
                self.assertEqual([b"\x01\x00"], output)
                self.assertFalse(task.done())
                self.assertEqual([], list(self.repository.rglob("*.wav")))
                with self.assertRaises(HTTPException) as busy:
                    await self.issuer.preview_stream("bright-guide")
                self.assertEqual(409, busy.exception.status_code)
            finally:
                proceed.set()
                await task
            self.assertEqual(b"\x01\x00\x02\x00", b"".join(output))
            output.clear()
            cached = await self.issuer.preview_stream("warm-companion")
            self.assertEqual("HIT", cached.headers["x-simo-cache"])
            await self._run(cached, send)
            self.assertEqual(b"\x01\x00\x02\x00", b"".join(output))
            self.assertEqual(1, Synthesizer.calls)

    async def test_cancelled_preview_never_commits_cache_and_releases_lease(self) -> None:
        first_sent = asyncio.Event()
        closed = asyncio.Event()

        class Synthesizer:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            async def synthesize(self, text: str) -> AsyncIterator[AudioChunk]:
                try:
                    yield AudioChunk(b"\x01\x00", 24_000)
                    await asyncio.Event().wait()
                finally:
                    closed.set()

        async def send(message: Message) -> None:
            if message.get("body"):
                first_sent.set()

        with patch("simo.lan_site.BreezeHTTPSynthesizer", Synthesizer):
            response = await self.issuer.preview_stream("warm-companion")
            task = asyncio.create_task(self._run(response, send))
            await asyncio.wait_for(first_sent.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(closed.is_set())
        self.assertFalse(self.issuer._preview_lock.locked())
        self.assertEqual([], list(self.repository.rglob("*.wav")))
        self.assertEqual([], list(self.repository.rglob("*.tmp")))

    async def test_header_send_failure_releases_never_started_response(self) -> None:
        async def send(message: Message) -> None:
            raise OSError("disconnected before headers")

        response = await self.issuer.preview_stream("warm-companion")
        with self.assertRaises(ClientDisconnect):
            await self._run(response, send)
        self.assertFalse(self.issuer._preview_lock.locked())
        self.assertEqual([], list(self.repository.rglob("*.tmp")))

    async def test_cache_key_includes_runtime_cfg_and_seed(self) -> None:
        preset = VOICE_PREVIEW_PRESETS[0]
        original = self.issuer._preview_path(preset, "runtime-one")
        self.assertNotEqual(original, self.issuer._preview_path(preset, "runtime-two"))
        self.assertNotEqual(
            original, self.issuer._preview_path(replace(preset, seed=200), "runtime-one")
        )
        self.issuer._config = replace(self.issuer._config, tts_cfg_scale=1.0)
        self.assertNotEqual(original, self.issuer._preview_path(preset, "runtime-one"))

    @staticmethod
    async def _run(response: Response, send: Send) -> None:
        scope: Scope = {"type": "http", "asgi": {"spec_version": "2.4"}}

        async def receive() -> Message:
            return {"type": "http.disconnect"}

        await response(scope, receive, send)
