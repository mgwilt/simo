#!/usr/bin/env python3
"""Run the pinned Breeze MPS fork on Apple Silicon."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BREEZE_SOURCE_REVISION = "a38d7d1b232dce058cc4e0bf78dc4aa3e0aca2ab"
BREEZE_MODEL_REVISION = "799624c0b4a1daa8db6d28bbd9850043c0270734"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve Breeze-TTS-2 through PyTorch MPS")
    parser.add_argument("model", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--device", default="mps", choices=("mps", "cpu"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
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

    upstream._settings = upstream.ApiSettings(  # noqa: SLF001 - pinned integration seam.
        model=args.model,
        fast_all=False,
        fast_text_encoder=False,
        fast_backbone_prefill=False,
        fast_backbone_decode=False,
        fast_depth_decoder=False,
        fast_codec=False,
        device=args.device,
    )
    upstream.app.router.routes[:] = [
        route for route in upstream.app.router.routes if getattr(route, "path", None) != "/health"
    ]

    @upstream.app.get("/health")
    def health() -> JSONResponse:
        ready = hasattr(upstream.app.state, "runtime")
        return JSONResponse(
            {
                "status": "ready" if ready else "loading",
                "busy": upstream._request_lock.locked(),  # noqa: SLF001
                "device": args.device,
                "dtype": "bfloat16" if args.device == "mps" else "float32",
                "sample_rate": (upstream.app.state.runtime.sample_rate if ready else None),
                "source_revision": BREEZE_SOURCE_REVISION,
                "model_revision": BREEZE_MODEL_REVISION,
            },
            status_code=200 if ready else 503,
        )

    uvicorn.run(upstream.app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
