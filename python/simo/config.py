"""Typed, environment-backed Simo runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Mapping, Self

QWEN_TTS_MODEL = "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-6bit"
PARAKEET_STT_MODEL = "mlx-community/parakeet-tdt-0.6b-v3"
QWEN_TEXT_MODEL = "mlx-community/Qwen3.5-4B-4bit"
QWEN_TTS_REVISION = "7dc92af14613355896fcab13b268c19ede233139"
PARAKEET_STT_REVISION = "ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15"
QWEN_TEXT_REVISION = "0e7ffd5c629ef7719d4cbc04069232580bfa9d9c"


class RunMode(StrEnum):
    """Runtime capability level requested by the operator."""

    HEADLESS = "headless"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class ModelConfig:
    model_id: str
    revision: str
    local_path: Path
    required_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """One immutable configuration snapshot for a Simo process."""

    mode: RunMode
    repository: Path
    models_dir: Path
    core_library: Path | None
    queue_capacity: int
    max_segments: int
    context_max_chars: int
    context_max_age_ms: int
    audio_input_device_index: int | None
    audio_output_device_index: int | None
    vad_start_rms: float
    vad_start_ms: int
    vad_stop_ms: int
    vad_pre_roll_ms: int
    max_utterance_s: float
    tts_voice: str
    tts_streaming_interval_s: float
    tts: ModelConfig
    stt: ModelConfig
    text: ModelConfig

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        mode: RunMode | str | None = None,
    ) -> Self:
        values = os.environ if environ is None else environ
        repository = Path(__file__).resolve().parents[2]
        models_dir = Path(values.get("SIMO_MODELS_DIR", repository / ".models"))
        configured_library = values.get("SIMO_CORE_LIBRARY")
        selected_mode = RunMode(mode or values.get("SIMO_MODE", RunMode.HEADLESS))
        queue_capacity = _positive_integer(values, "SIMO_QUEUE_CAPACITY", 256)
        max_segments = _positive_integer(values, "SIMO_MAX_SEGMENTS", 64)
        context_max_chars = _positive_integer(values, "SIMO_CONTEXT_MAX_CHARS", 8_000)
        context_max_age_ms = _positive_integer(values, "SIMO_CONTEXT_MAX_AGE_MS", 1_000)
        audio_input_device_index = _optional_nonnegative_integer(
            values,
            "SIMO_AUDIO_INPUT_DEVICE_INDEX",
        )
        audio_output_device_index = _optional_nonnegative_integer(
            values,
            "SIMO_AUDIO_OUTPUT_DEVICE_INDEX",
        )
        vad_start_rms = _positive_float(values, "SIMO_VAD_START_RMS", 0.02)
        if vad_start_rms > 1:
            raise ValueError("SIMO_VAD_START_RMS must not exceed 1")
        vad_start_ms = _positive_integer(values, "SIMO_VAD_START_MS", 60)
        vad_stop_ms = _positive_integer(values, "SIMO_VAD_STOP_MS", 500)
        vad_pre_roll_ms = _positive_integer(values, "SIMO_VAD_PRE_ROLL_MS", 200)
        max_utterance_s = _positive_float(values, "SIMO_MAX_UTTERANCE_S", 30.0)
        tts_voice = values.get("SIMO_TTS_VOICE", "Aiden").strip()
        if not tts_voice:
            raise ValueError("SIMO_TTS_VOICE must not be empty")
        tts_streaming_interval_s = _positive_float(
            values,
            "SIMO_TTS_STREAMING_INTERVAL_S",
            0.32,
        )

        def model(
            env_name: str,
            revision_env_name: str,
            default_id: str,
            default_revision: str,
            required_paths: tuple[str, ...],
        ) -> ModelConfig:
            model_id = values.get(env_name, default_id).strip()
            if not model_id:
                raise ValueError(f"{env_name} must not be empty")
            revision = values.get(revision_env_name, default_revision).strip()
            if not revision:
                raise ValueError(f"{revision_env_name} must not be empty")
            directory = model_id.rsplit("/", 1)[-1]
            return ModelConfig(
                model_id=model_id,
                revision=revision,
                local_path=models_dir / directory,
                required_paths=required_paths,
            )

        return cls(
            mode=selected_mode,
            repository=repository,
            models_dir=models_dir,
            core_library=Path(configured_library) if configured_library else None,
            queue_capacity=queue_capacity,
            max_segments=max_segments,
            context_max_chars=context_max_chars,
            context_max_age_ms=context_max_age_ms,
            audio_input_device_index=audio_input_device_index,
            audio_output_device_index=audio_output_device_index,
            vad_start_rms=vad_start_rms,
            vad_start_ms=vad_start_ms,
            vad_stop_ms=vad_stop_ms,
            vad_pre_roll_ms=vad_pre_roll_ms,
            max_utterance_s=max_utterance_s,
            tts_voice=tts_voice,
            tts_streaming_interval_s=tts_streaming_interval_s,
            tts=model(
                "SIMO_TTS_MODEL",
                "SIMO_TTS_REVISION",
                QWEN_TTS_MODEL,
                QWEN_TTS_REVISION,
                (
                    "config.json",
                    "model.safetensors",
                    "speech_tokenizer/config.json",
                    "speech_tokenizer/model.safetensors",
                ),
            ),
            stt=model(
                "SIMO_STT_MODEL",
                "SIMO_STT_REVISION",
                PARAKEET_STT_MODEL,
                PARAKEET_STT_REVISION,
                ("config.json", "model.safetensors", "tokenizer.model"),
            ),
            text=model(
                "SIMO_TEXT_MODEL",
                "SIMO_TEXT_REVISION",
                QWEN_TEXT_MODEL,
                QWEN_TEXT_REVISION,
                ("config.json", "model.safetensors", "tokenizer.json"),
            ),
        )


def _positive_integer(values: Mapping[str, str], name: str, default: int) -> int:
    raw = values.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _positive_float(values: Mapping[str, str], name: str, default: float) -> float:
    raw = values.get(name, str(default))
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive number") from error
    if value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return value


def _optional_nonnegative_integer(
    values: Mapping[str, str],
    name: str,
) -> int | None:
    raw = values.get(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a non-negative integer") from error
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value
