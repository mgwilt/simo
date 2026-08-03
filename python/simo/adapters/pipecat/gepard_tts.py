"""Pipecat TTS service for the open-source Gepard reference HTTP server."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import aiohttp
from pipecat.frames.frames import ErrorFrame, Frame, StartFrame, TTSAudioRawFrame
from pipecat.services.tts_service import TTSService

from simo.gepard import (
    GEPARD_SAMPLE_RATE,
    GepardRequest,
    decode_gepard_wav,
    iter_pcm_chunks,
)


class GepardTTSService(TTSService):
    """Adapt Gepard's batch WAV endpoint to bounded Pipecat audio frames."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8000",
        aiohttp_session: aiohttp.ClientSession | None = None,
        reference: str | None = None,
        cfg_scale: float | None = None,
        chunk_duration_ms: int = 20,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            sample_rate=GEPARD_SAMPLE_RATE,
            push_start_frame=True,
            push_stop_frames=True,
            **kwargs,
        )
        if chunk_duration_ms <= 0:
            raise ValueError("chunk_duration_ms must be positive")
        self._base_url = base_url.rstrip("/")
        self._session = aiohttp_session
        self._owns_session = aiohttp_session is None
        self._reference = reference
        self._cfg_scale = cfg_scale
        self._chunk_duration_ms = chunk_duration_ms

    def can_generate_metrics(self) -> bool:
        return True

    async def start(self, frame: StartFrame) -> None:
        await super().start(frame)
        if self._owns_session:
            self._session = aiohttp.ClientSession()

    async def cleanup(self) -> None:
        await super().cleanup()
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def run_tts(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        text: str,
        context_id: str,
    ) -> AsyncGenerator[Frame, None]:
        try:
            if self._session is None:
                raise RuntimeError(
                    "HTTP session is not initialized; call start() before run_tts()"
                )
            request = GepardRequest(text, self._reference, self._cfg_scale)
            async with self._session.post(
                f"{self._base_url}/synthesize",
                json=request.as_payload(),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    yield ErrorFrame(
                        error=f"Gepard API error (status {response.status}): {error_text}"
                    )
                    return
                wav_data = await response.read()

            audio = decode_gepard_wav(wav_data)
            await self.start_tts_usage_metrics(text)
            first = True
            for chunk in iter_pcm_chunks(
                audio, chunk_duration_ms=self._chunk_duration_ms
            ):
                if first:
                    await self.stop_ttfb_metrics()
                    first = False
                yield TTSAudioRawFrame(
                    audio=chunk,
                    sample_rate=audio.sample_rate,
                    num_channels=audio.channels,
                    context_id=context_id,
                )
        except (aiohttp.ClientError, OSError, RuntimeError, ValueError) as error:
            yield ErrorFrame(error=f"Gepard synthesis failed: {error}")
        finally:
            await self.stop_ttfb_metrics()
