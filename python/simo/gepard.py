"""Gepard reference-server request and PCM/WAV boundary."""

from __future__ import annotations

import io
import json
import wave
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GEPARD_SAMPLE_RATE = 22_050


@dataclass(frozen=True, slots=True)
class GepardRequest:
    text: str
    reference: str | None = None
    cfg_scale: float | None = None

    def as_payload(self) -> dict[str, str | float]:
        if not self.text.strip():
            raise ValueError("Gepard text must not be empty")
        payload: dict[str, str | float] = {"text": self.text}
        if self.reference is not None:
            payload["reference"] = self.reference
        if self.cfg_scale is not None:
            payload["cfg_scale"] = self.cfg_scale
        return payload


@dataclass(frozen=True, slots=True)
class PcmAudio:
    data: bytes
    sample_rate: int
    channels: int
    sample_width: int


class GepardHttpClient:
    """Small synchronous client for the open-source reference server.

    Realtime frameworks should call this outside their event-loop thread or use
    their own asynchronous transport, as the Pipecat adapter does.
    """

    def __init__(
        self, base_url: str = "http://127.0.0.1:8000", *, timeout_s: float = 30.0
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._url = f"{base_url.rstrip('/')}/synthesize"
        self._timeout_s = timeout_s

    def synthesize(self, request: GepardRequest) -> PcmAudio:
        encoded = json.dumps(request.as_payload()).encode("utf-8")
        http_request = Request(
            self._url,
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=self._timeout_s) as response:
                status = int(getattr(response, "status", 200))
                body = response.read()
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Gepard API error (status {error.code}): {detail}"
            ) from error
        except URLError as error:
            raise RuntimeError(f"Gepard API request failed: {error.reason}") from error
        if status != 200:
            raise RuntimeError(f"Gepard API error (status {status})")
        return decode_gepard_wav(body)


def decode_gepard_wav(data: bytes) -> PcmAudio:
    """Validate the reference server's WAV and return interleaved PCM bytes."""

    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except (EOFError, wave.Error) as error:
        raise ValueError("Gepard response is not a valid WAV file") from error

    if channels != 1:
        raise ValueError(f"Gepard WAV must be mono, got {channels} channels")
    if sample_width != 2:
        raise ValueError(f"Gepard WAV must use 16-bit PCM, got {sample_width * 8}-bit")
    if sample_rate != GEPARD_SAMPLE_RATE:
        raise ValueError(
            f"Gepard WAV must use {GEPARD_SAMPLE_RATE} Hz, got {sample_rate} Hz"
        )
    return PcmAudio(frames, sample_rate, channels, sample_width)


def iter_pcm_chunks(audio: PcmAudio, *, chunk_duration_ms: int = 20) -> Iterator[bytes]:
    """Split PCM on complete sample frames using a deterministic duration."""

    if chunk_duration_ms <= 0:
        raise ValueError("chunk_duration_ms must be positive")
    frame_bytes = audio.channels * audio.sample_width
    frames_per_chunk = max(1, round(audio.sample_rate * chunk_duration_ms / 1_000))
    chunk_bytes = frames_per_chunk * frame_bytes
    for offset in range(0, len(audio.data), chunk_bytes):
        chunk = audio.data[offset : offset + chunk_bytes]
        if len(chunk) % frame_bytes != 0:
            raise ValueError("PCM payload ends with a partial sample frame")
        yield chunk
