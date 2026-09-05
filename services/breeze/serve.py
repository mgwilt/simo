#!/usr/bin/env python3
"""Run the pinned Breeze MPS fork on Apple Silicon."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

BREEZE_MODEL_REVISION = "799624c0b4a1daa8db6d28bbd9850043c0270734"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve Breeze-TTS-2 through PyTorch MPS")
    parser.add_argument("model", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--device", default="mps", choices=("mps", "cpu"))
    parser.add_argument("--performance-mode", default="quality", choices=("quality", "fast"))
    parser.add_argument("--experimental-recipe", choices=("mlx-int8-v1",))
    parser.add_argument("--engine", default="streaming", choices=("streaming", "reference"))
    parser.add_argument("--attention", default="eager", choices=("eager", "sdpa"))
    parser.add_argument("--quantization", default="none", choices=("none", "int8", "int4"))
    parser.add_argument(
        "--depth-cache", default="dynamic", choices=("dynamic", "static", "compiled")
    )
    return parser


def model_identity(model: Path) -> dict[str, object]:
    """Hash the loaded package, not just its claimed download revision."""
    marker = json.loads((model / ".simo-model.json").read_text())
    if (
        marker.get("model_id") != "BreezeBlue/Breeze-TTS-2"
        or marker.get("revision") != BREEZE_MODEL_REVISION
    ):
        raise RuntimeError("This service requires Simo's pinned Breeze-TTS-2 model package")
    digest = hashlib.sha256()
    for path in sorted(model.rglob("*")):
        if path.is_file() and path.suffix in (".json", ".safetensors", ".model", ".txt"):
            digest.update(str(path.relative_to(model)).encode())
            with path.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    digest.update(block)
    return {"model_revision": marker["revision"], "model_digest": digest.hexdigest()}


def runtime_identity(source: Path, args: argparse.Namespace) -> dict[str, object]:
    """Fingerprint executable source and settings, including uncommitted edits."""
    digest = hashlib.sha256()
    for directory in (source / "breeze_infer", source / "models"):
        for path in sorted(directory.rglob("*.py")):
            digest.update(str(path.relative_to(source)).encode())
            digest.update(path.read_bytes())
    digest.update(Path(__file__).read_bytes())
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    identity: dict[str, object] = {
        "source_revision": revision,
        "source_digest": digest.hexdigest(),
        **model_identity(args.model),
        "device": args.device,
        "dtype": "bfloat16",
        "engine": args.engine,
        "attention": args.attention,
        "quantization": args.quantization,
        "depth_cache": args.depth_cache,
        "performance_mode": (
            "candidate"
            if args.attention != "eager"
            or args.quantization != "none"
            or args.depth_cache != "dynamic"
            else args.performance_mode
        ),
        "cached_depth_cfg": args.engine == "streaming",
        "codec_chunk_frames": 1 if args.engine == "streaming" else None,
        "cfg_policy": "request",
        "sampling": {
            "temperature": 0.9,
            "top_k": 50,
            "top_p": 1.0,
            "repetition_penalty": 1.0,
            "max_new_tokens": 750,
        },
        "dependencies": {
            name: importlib.metadata.version(name) for name in ("torch", "transformers", "qwen-tts")
        },
        "os": platform.platform(),
    }
    if getattr(args, "experimental_recipe", None) is not None:
        identity["experimental_recipe"] = args.experimental_recipe
        identity["performance_mode"] = "experimental"
        identity["release_accepted"] = False
    identity["runtime_fingerprint"] = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode()
    ).hexdigest()
    return identity


def main() -> int:
    args = build_parser().parse_args()
    if args.performance_mode == "fast":
        raise RuntimeError(
            "Fast has no released recipe yet: latency, sustained playback, and listening gates must pass. Use quality, or explicit experimental --attention/--quantization settings."
        )
    if args.quantization != "none" and args.device != "mps":
        raise RuntimeError("Native quantization candidates require MPS")
    if args.experimental_recipe is not None and (
        args.device != "mps"
        or args.engine != "streaming"
        or args.attention != "eager"
        or args.quantization != "none"
        or args.depth_cache != "dynamic"
        or args.host != "127.0.0.1"
        or args.port == 7860
    ):
        raise RuntimeError(
            "Experimental MLX requires MPS streaming, unchanged reference flags, and a separate loopback port"
        )
    repository = Path(__file__).resolve().parents[2]
    source = repository / "vendor" / "breeze-tts"
    if not (source / "breeze_infer" / "api.py").is_file():
        raise RuntimeError("pinned Breeze submodule is unavailable; initialize submodules")
    if not args.model.is_dir():
        raise RuntimeError(f"Breeze model directory is unavailable: {args.model}")
    sys.path.insert(0, str(source))

    import breeze_infer.api as upstream
    import torch
    import uvicorn
    from fastapi.responses import JSONResponse

    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("PyTorch MPS is unavailable on this machine")

    identity = runtime_identity(source, args)
    started = time.perf_counter()
    upstream._settings = upstream.ApiSettings(  # noqa: SLF001 - pinned integration seam.
        model=args.model,
        fast_all=False,
        fast_text_encoder=False,
        fast_backbone_prefill=False,
        fast_backbone_decode=False,
        fast_depth_decoder=False,
        fast_codec=False,
        device=args.device,
        engine=args.engine,
        attention=args.attention,
        quantization=args.quantization,
        runtime_fingerprint=str(identity["runtime_fingerprint"]),
        depth_cache=args.depth_cache,
        experimental_recipe=args.experimental_recipe,
        runtime_identity=identity,
    )
    upstream.app.router.routes[:] = [
        route for route in upstream.app.router.routes if getattr(route, "path", None) != "/health"
    ]

    @upstream.app.get("/health")
    def health() -> JSONResponse:
        loaded = hasattr(upstream.app.state, "runtime")
        poisoned = loaded and getattr(upstream.app.state.runtime, "_poisoned", False)
        ready = loaded and not poisoned
        parameter = next(upstream.app.state.model.parameters()) if loaded else None
        return JSONResponse(
            {
                **(getattr(upstream.app.state, "runtime_identity", None) or identity),
                "status": "ready" if ready else ("unavailable" if poisoned else "loading"),
                "busy": upstream._request_lock.locked(),  # noqa: SLF001
                "device": args.device,
                "dtype": str(parameter.dtype).removeprefix("torch.")
                if parameter is not None
                else None,
                "sample_rate": (upstream.app.state.runtime.sample_rate if ready else None),
                "uptime_s": time.perf_counter() - started,
                "load_s": getattr(upstream.app.state, "load_s", None),
                "depth_warmup_s": getattr(upstream.app.state, "depth_warmup_s", None),
                "last_request": getattr(upstream.app.state.runtime, "last_metrics", {})
                if ready
                else {},
                "quantization_inventory": getattr(upstream.app.state, "quantization", None),
            },
            status_code=200 if ready else 503,
        )

    uvicorn.run(upstream.app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
