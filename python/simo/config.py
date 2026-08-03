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


class RunMode(StrEnum):
    """Runtime capability level requested by the operator."""

    HEADLESS = "headless"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class ModelConfig:
    model_id: str
    local_path: Path


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
        context_max_age_ms = _positive_integer(
            values, "SIMO_CONTEXT_MAX_AGE_MS", 1_000
        )

        def model(env_name: str, default_id: str) -> ModelConfig:
            model_id = values.get(env_name, default_id).strip()
            if not model_id:
                raise ValueError(f"{env_name} must not be empty")
            directory = model_id.rsplit("/", 1)[-1]
            return ModelConfig(model_id=model_id, local_path=models_dir / directory)

        return cls(
            mode=selected_mode,
            repository=repository,
            models_dir=models_dir,
            core_library=Path(configured_library) if configured_library else None,
            queue_capacity=queue_capacity,
            max_segments=max_segments,
            context_max_chars=context_max_chars,
            context_max_age_ms=context_max_age_ms,
            tts=model("SIMO_TTS_MODEL", QWEN_TTS_MODEL),
            stt=model("SIMO_STT_MODEL", PARAKEET_STT_MODEL),
            text=model("SIMO_TEXT_MODEL", QWEN_TEXT_MODEL),
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
