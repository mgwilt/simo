"""Privacy-safe aggregate diagnostics for local microphone calibration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np


@dataclass(frozen=True, slots=True)
class LevelSummary:
    blocks: int
    mean_rms: float
    median_rms: float
    p95_rms: float
    peak_rms: float


Cue = Literal["start", "finish", "failed"]


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
    ambient_ceiling = ambient.peak_rms
    speech_level = speech.p95_rms
    separated = speech_level >= ambient.p95_rms * 1.15 and speech_level - ambient_ceiling >= 0.002
    recommendation = round((ambient_ceiling + speech_level) / 2, 6) if separated else None
    return {
        "schema_version": 1,
        "ready": separated,
        "privacy": "aggregate RMS only; no audio stored or transcribed",
        "ambient": asdict(ambient),
        "speech": asdict(speech),
        "configured_start_rms": configured_start_rms,
        "recommended_start_rms": recommendation,
        "environment": (f"SIMO_VAD_START_RMS={recommendation}" if recommendation else None),
        "detail": (
            "sustained speech energy is separated from peak ambient energy"
            if separated
            else "speech was not sufficiently louder than ambient; check mute and retry"
        ),
    }


def collect_interactive_levels(
    read_rms: Callable[[], float],
    cue: Callable[[Cue], None],
    *,
    ambient_blocks: int,
    speech_blocks: int,
    onset_timeout_blocks: int,
) -> tuple[list[float], list[float], float]:
    """Control ambient, onset, and speech capture without user-timed phases."""

    if min(ambient_blocks, speech_blocks, onset_timeout_blocks) <= 0:
        raise ValueError("interactive calibration bounds must be positive")
    if speech_blocks < 3:
        raise ValueError("interactive calibration requires at least three speech blocks")
    ambient = [read_rms() for _ in range(ambient_blocks)]
    ambient_ceiling = summarize_levels(ambient).p95_rms
    onset_trigger = max(ambient_ceiling * 1.35, ambient_ceiling + 0.002)
    cue("start")

    candidate: list[float] = []
    for _ in range(onset_timeout_blocks):
        value = read_rms()
        if value >= onset_trigger:
            candidate.append(value)
            if len(candidate) >= 3:
                break
        else:
            candidate.clear()
    else:
        cue("failed")
        raise RuntimeError("no speech onset detected after the start tone")

    speech = candidate[:]
    speech.extend(read_rms() for _ in range(speech_blocks - len(speech)))
    cue("finish")
    return ambient, speech, round(onset_trigger, 6)


def run_interactive_calibration(
    *,
    configured_start_rms: float,
    input_device_index: int | None = None,
    output_device_index: int | None = None,
    ambient_seconds: float = 2.0,
    speech_seconds: float = 3.0,
    onset_timeout_seconds: float = 15.0,
    audio_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Drive calibration with audible cues and automatic speech onset detection."""

    if min(ambient_seconds, speech_seconds, onset_timeout_seconds) <= 0:
        raise ValueError("interactive calibration durations must be positive")
    if audio_factory is None:
        import pyaudio

        audio_factory = pyaudio.PyAudio
    import pyaudio

    input_rate = 16_000
    output_rate = 24_000
    frames_per_buffer = 320
    audio = audio_factory()
    input_stream = None
    output_stream = None
    try:
        input_kwargs: dict[str, Any] = {
            "format": pyaudio.paInt16,
            "channels": 1,
            "rate": input_rate,
            "input": True,
            "frames_per_buffer": frames_per_buffer,
        }
        if input_device_index is not None:
            input_kwargs["input_device_index"] = input_device_index
        output_kwargs: dict[str, Any] = {
            "format": pyaudio.paInt16,
            "channels": 1,
            "rate": output_rate,
            "output": True,
            "frames_per_buffer": 2_400,
        }
        if output_device_index is not None:
            output_kwargs["output_device_index"] = output_device_index
        input_stream = audio.open(**input_kwargs)
        output_stream = audio.open(**output_kwargs)

        def read_rms() -> float:
            pcm = input_stream.read(frames_per_buffer, exception_on_overflow=False)
            samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
            return float(np.sqrt(np.mean(samples * samples)))

        def cue(kind: Cue) -> None:
            frequencies = {
                "start": (880,),
                "finish": (880, 880),
                "failed": (220, 180),
            }[kind]
            _play_tones(output_stream, frequencies, sample_rate=output_rate)

        blocks_per_second = input_rate / frames_per_buffer
        ambient, speech, onset_trigger = collect_interactive_levels(
            read_rms,
            cue,
            ambient_blocks=round(ambient_seconds * blocks_per_second),
            speech_blocks=round(speech_seconds * blocks_per_second),
            onset_timeout_blocks=round(onset_timeout_seconds * blocks_per_second),
        )
        result = calibration_result(
            ambient,
            speech,
            configured_start_rms=configured_start_rms,
        )
        result.update(
            {
                "interaction": "one tone starts speech; two tones finish",
                "onset_trigger_rms": onset_trigger,
            }
        )
        return result
    finally:
        for stream in (input_stream, output_stream):
            if stream is not None:
                stream.stop_stream()
                stream.close()
        audio.terminate()


def _play_tones(
    stream: Any,
    frequencies: tuple[int, ...],
    *,
    sample_rate: int,
) -> None:
    tone_samples = round(sample_rate * 0.18)
    silence = b"\x00\x00" * round(sample_rate * 0.12)
    positions = np.arange(tone_samples, dtype=np.float32) / sample_rate
    for index, frequency in enumerate(frequencies):
        wave = np.sin(2 * np.pi * frequency * positions) * 0.18
        stream.write((wave * 32767).astype("<i2").tobytes())
        if index + 1 < len(frequencies):
            stream.write(silence)
