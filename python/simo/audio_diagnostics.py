"""Privacy-safe aggregate diagnostics for local microphone calibration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

import numpy as np


@dataclass(frozen=True, slots=True)
class LevelSummary:
    blocks: int
    mean_rms: float
    median_rms: float
    p95_rms: float
    peak_rms: float


def capture_rms_blocks(
    seconds: float,
    *,
    device_index: int | None = None,
    audio_factory: Callable[[], Any] | None = None,
    sample_rate: int = 16_000,
    frames_per_buffer: int = 320,
) -> list[float]:
    """Capture only per-block RMS values; raw PCM is never retained or returned."""

    if seconds <= 0:
        raise ValueError("capture seconds must be positive")
    if sample_rate <= 0 or frames_per_buffer <= 0:
        raise ValueError("audio bounds must be positive")
    if audio_factory is None:
        import pyaudio

        audio_factory = pyaudio.PyAudio
    audio = audio_factory()
    stream = None
    values: list[float] = []
    try:
        import pyaudio

        kwargs: dict[str, Any] = {
            "format": pyaudio.paInt16,
            "channels": 1,
            "rate": sample_rate,
            "input": True,
            "frames_per_buffer": frames_per_buffer,
        }
        if device_index is not None:
            kwargs["input_device_index"] = device_index
        stream = audio.open(**kwargs)
        target_blocks = max(1, round(seconds * sample_rate / frames_per_buffer))
        for _ in range(target_blocks):
            pcm = stream.read(frames_per_buffer, exception_on_overflow=False)
            samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
            values.append(float(np.sqrt(np.mean(samples * samples))))
    finally:
        if stream is not None:
            stream.stop_stream()
            stream.close()
        audio.terminate()
    return values


def summarize_levels(values: list[float]) -> LevelSummary:
    if not values:
        raise ValueError("level summary requires at least one block")
    samples = np.asarray(values, dtype=np.float64)
    return LevelSummary(
        blocks=len(values),
        mean_rms=round(float(samples.mean()), 6),
        median_rms=round(float(np.median(samples)), 6),
        p95_rms=round(float(np.percentile(samples, 95)), 6),
        peak_rms=round(float(samples.max()), 6),
    )


def calibration_result(
    ambient_values: list[float],
    speech_values: list[float],
    *,
    configured_start_rms: float,
) -> dict[str, Any]:
    """Recommend a threshold only when speech separates clearly from ambience."""

    ambient = summarize_levels(ambient_values)
    speech = summarize_levels(speech_values)
    ambient_ceiling = ambient.p95_rms
    speech_level = speech.median_rms
    separated = (
        speech_level >= ambient_ceiling * 1.5
        and speech_level - ambient_ceiling >= 0.003
    )
    recommendation = (
        round((ambient_ceiling + speech_level) / 2, 6) if separated else None
    )
    return {
        "schema_version": 1,
        "ready": separated,
        "privacy": "aggregate RMS only; no audio stored or transcribed",
        "ambient": asdict(ambient),
        "speech": asdict(speech),
        "configured_start_rms": configured_start_rms,
        "recommended_start_rms": recommendation,
        "environment": (
            f"SIMO_VAD_START_RMS={recommendation}" if recommendation else None
        ),
        "detail": (
            "speech and ambient levels are sufficiently separated"
            if separated
            else "speech was not sufficiently louder than ambient; check mute and retry"
        ),
    }
