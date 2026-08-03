#!/usr/bin/env python3
"""Plan or explicitly download Simo's pinned local model repositories."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from simo.config import ModelConfig, RunMode, RuntimeConfig

MODEL_BYTES = {
    "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-6bit": 1_833_590_308,
    "mlx-community/parakeet-tdt-0.6b-v3": 2_509_044_141,
    "mlx-community/Qwen3.5-4B-4bit": 3_061_130_647,
}
MINIMUM_OVERHEAD_BYTES = 2 * 1024**3
OVERHEAD_RATIO = 1.25


@dataclass(frozen=True, slots=True)
class ModelPlan:
    role: str
    config: ModelConfig
    expected_bytes: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "model_id": self.config.model_id,
            "revision": self.config.revision,
            "target": str(self.config.local_path),
            "expected_bytes": self.expected_bytes,
            "expected_gib": round(self.expected_bytes / 1024**3, 2),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or explicitly download Simo's pinned model weights"
    )
    parser.add_argument(
        "--accept-download",
        action="store_true",
        help="perform the large downloads; without this flag the command only prints a plan",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=("tts", "stt", "text"),
        help="limit the plan/download to one role; repeat as needed",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = RuntimeConfig.from_environment(mode=RunMode.LIVE)
    selected = set(args.only or ("tts", "stt", "text"))
    plans = [plan for plan in model_plans(config) if plan.role in selected]
    payload = plan_payload(config, plans, accepted=args.accept_download)
    print(json.dumps(payload, indent=2))
    if not args.accept_download:
        return 0
    ensure_disk_space(config.models_dir, payload["required_free_bytes"])
    download_models(plans)
    return 0


def model_plans(config: RuntimeConfig) -> list[ModelPlan]:
    return [
        ModelPlan("tts", config.tts, MODEL_BYTES.get(config.tts.model_id, 0)),
        ModelPlan("stt", config.stt, MODEL_BYTES.get(config.stt.model_id, 0)),
        ModelPlan("text", config.text, MODEL_BYTES.get(config.text.model_id, 0)),
    ]


def plan_payload(
    config: RuntimeConfig,
    plans: list[ModelPlan],
    *,
    accepted: bool = False,
) -> dict[str, Any]:
    expected = sum(plan.expected_bytes for plan in plans)
    required = int(expected * OVERHEAD_RATIO) + MINIMUM_OVERHEAD_BYTES
    return {
        "schema_version": 1,
        "action": "download" if accepted else "plan",
        "models_dir": str(config.models_dir),
        "models": [plan.as_dict() for plan in plans],
        "expected_bytes": expected,
        "expected_gib": round(expected / 1024**3, 2),
        "required_free_bytes": required,
        "required_free_gib": round(required / 1024**3, 2),
        "requires_explicit_flag": "--accept-download",
    }


def ensure_disk_space(models_dir: Path, required_free_bytes: int) -> None:
    models_dir.parent.mkdir(parents=True, exist_ok=True)
    available = shutil.disk_usage(models_dir.parent).free
    if available < required_free_bytes:
        raise RuntimeError(
            f"insufficient free space: need {required_free_bytes} bytes, have {available}"
        )


def download_models(
    plans: list[ModelPlan],
    *,
    downloader: Callable[..., str] | None = None,
) -> None:
    if downloader is None:
        from huggingface_hub import snapshot_download

        downloader = snapshot_download
    for plan in plans:
        if marker_is_current(plan.config):
            print(f"already installed: {plan.role} {plan.config.local_path}")
            continue
        plan.config.local_path.mkdir(parents=True, exist_ok=True)
        downloader(
            repo_id=plan.config.model_id,
            revision=plan.config.revision,
            local_dir=str(plan.config.local_path),
            max_workers=4,
        )
        verify_required_files(plan.config)
        write_marker(plan.config)
        print(f"installed: {plan.role} {plan.config.local_path}")


def verify_required_files(config: ModelConfig) -> None:
    missing = [
        relative
        for relative in config.required_paths
        if not (config.local_path / relative).is_file()
    ]
    if missing:
        raise RuntimeError(
            f"download for {config.model_id} is incomplete; missing {', '.join(missing)}"
        )


def marker_is_current(config: ModelConfig) -> bool:
    try:
        marker = json.loads((config.local_path / ".simo-model.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    return (
        marker.get("model_id") == config.model_id
        and marker.get("revision") == config.revision
        and all((config.local_path / path).is_file() for path in config.required_paths)
    )


def write_marker(config: ModelConfig) -> None:
    payload = {
        "schema_version": 1,
        "model_id": config.model_id,
        "revision": config.revision,
        "required_paths": list(config.required_paths),
    }
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=config.local_path,
        prefix=".simo-model-",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        json.dump(payload, temporary, indent=2)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(config.local_path / ".simo-model.json")


if __name__ == "__main__":
    raise SystemExit(main())
