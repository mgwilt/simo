from __future__ import annotations

import asyncio
import io
import os
import unittest
import wave
from pathlib import Path
from typing import Self

os.environ.setdefault(
    "NLTK_DATA",
    str(Path(__file__).resolve().parents[1] / "fixtures/nltk_data"),
)

from pipecat.frames.frames import (
    ErrorFrame,
    InterimTranscriptionFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
)
from pipecat.observers.base_observer import FramePushed
from simo.adapters.pipecat.gepard_tts import GepardTTSService
from simo.adapters.pipecat.observer import PipecatSemanticObserver
from simo.context import EnqueueResult
from simo.gepard import GEPARD_SAMPLE_RATE


class RecordingSink:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bool]] = []

    def enqueue_transcript(
        self, speaker: str, text: str, is_final: bool = True
    ) -> EnqueueResult:
        self.calls.append((speaker, text, is_final))
        return EnqueueResult(True, len(self.calls))


def make_wav() -> tuple[bytes, bytes]:
    pcm = b"\x01\x00" * 1_000
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(GEPARD_SAMPLE_RATE)
        wav.writeframes(pcm)
    return output.getvalue(), pcm


class FakeResponse:
    def __init__(self, *, status: int, body: bytes, text: str = "") -> None:
        self.status = status
        self._body = body
        self._text = text

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def read(self) -> bytes:
        return self._body

    async def text(self) -> str:
        return self._text


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requests: list[tuple[str, dict[str, object]]] = []

    def post(self, url: str, *, json: dict[str, object]) -> FakeResponse:
        self.requests.append((url, json))
        return self.response


class PipecatAdapterTests(unittest.TestCase):
    def test_observer_accepts_final_transcript_once(self) -> None:
        sink = RecordingSink()
        observer = PipecatSemanticObserver(sink)
        final = TranscriptionFrame(
            text="hello",
            user_id="user-1",
            timestamp="2026-08-02T00:00:00Z",
        )
        interim = InterimTranscriptionFrame(
            text="hel",
            user_id="user-1",
            timestamp="2026-08-02T00:00:00Z",
        )

        async def exercise() -> None:
            final_event = FramePushed(None, None, final, None, 0)  # type: ignore[arg-type]
            await observer.on_push_frame(final_event)
            await observer.on_push_frame(final_event)
            await observer.on_push_frame(
                FramePushed(None, None, interim, None, 0)  # type: ignore[arg-type]
            )

        asyncio.run(exercise())
        self.assertEqual([("user-1", "hello", True)], sink.calls)
        self.assertEqual(1, observer.semantic_bridge.stats().duplicate)

    def test_gepard_service_posts_and_yields_pcm_frames(self) -> None:
        wav, expected_pcm = make_wav()
        session = FakeSession(FakeResponse(status=200, body=wav))
        service = GepardTTSService(
            base_url="http://gepard.local/",
            aiohttp_session=session,  # type: ignore[arg-type]
            chunk_duration_ms=20,
        )

        async def collect() -> list[object]:
            return [frame async for frame in service.run_tts("hello", "context-1")]

        frames = asyncio.run(collect())
        self.assertEqual(
            [("http://gepard.local/synthesize", {"text": "hello"})],
            session.requests,
        )
        self.assertTrue(frames)
        self.assertTrue(all(isinstance(frame, TTSAudioRawFrame) for frame in frames))
        self.assertEqual(expected_pcm, b"".join(frame.audio for frame in frames))
        self.assertTrue(all(frame.context_id == "context-1" for frame in frames))

    def test_gepard_service_bounds_http_error(self) -> None:
        session = FakeSession(FakeResponse(status=503, body=b"", text="unavailable"))
        service = GepardTTSService(
            base_url="http://gepard.local",
            aiohttp_session=session,  # type: ignore[arg-type]
        )

        async def collect() -> list[object]:
            return [frame async for frame in service.run_tts("hello", "context-1")]

        frames = asyncio.run(collect())
        self.assertEqual(1, len(frames))
        self.assertIsInstance(frames[0], ErrorFrame)
        self.assertIn("503", frames[0].error)


if __name__ == "__main__":
    unittest.main()
