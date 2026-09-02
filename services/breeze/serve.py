#!/usr/bin/env python3
"""Run the pinned Breeze service on Apple Silicon without modifying upstream."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

BREEZE_SOURCE_REVISION = "0072588a517f54a3a91d8f566be91cce74b64d13"
BREEZE_MODEL_REVISION = "799624c0b4a1daa8db6d28bbd9850043c0270734"


def _force_nested_eager_attention() -> None:
    """Keep the nested T5Gemma encoder off CUDA-only FlashAttention 2."""
    from models.breeze import BreezeForConditionalGeneration

    original_init = BreezeForConditionalGeneration.__init__

    def apple_silicon_init(self: Any, config: Any, *args: Any, **kwargs: Any) -> None:
        # Upstream defaults only the nested text encoder to FlashAttention 2 even
        # when the top-level model is loaded with eager attention. Keep this
        # compatibility change in our wrapper so vendor/ remains pinned verbatim.
        config.text_encoder_config.preferred_attn_implementation = "eager"
        original_init(self, config, *args, **kwargs)

    BreezeForConditionalGeneration.__init__ = apple_silicon_init


class _AppleSiliconBreezeRuntime:
    """API-compatible eager runtime for devices unsupported by CUDA streaming."""

    fast_enabled = False

    def __init__(
        self,
        model: Any,
        audio_tokenizer: Any,
        _config: Any,
        *,
        tokenizer: Any | None = None,
    ) -> None:
        self.model = model
        self.audio_tokenizer = audio_tokenizer
        self.tokenizer = tokenizer
        self.sample_rate = int(model.config.codec_config.sampling_rate)

    def iter_audio_chunks(self, inputs: dict[str, Any], *, request_id: str | None = None) -> Any:
        del request_id
        generated = self.model.generate(
            **inputs,
            output_audio=True,
            audio_tokenizer=self.audio_tokenizer,
        )
        audio = generated.audio if hasattr(generated, "audio") else generated
        if not audio:
            return
        tensor = audio[0]
        while tensor.dim() > 1:
            tensor = tensor[0]
        samples = tensor.detach().float().cpu().numpy()
        chunk_samples = self.sample_rate // 10
        for start in range(0, len(samples), chunk_samples):
            yield SimpleNamespace(audio=samples[start : start + chunk_samples])


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

    _force_nested_eager_attention()
    upstream.resolve_device = lambda: args.device
    # The pinned upstream HTTP API always instantiates its CUDA-only streaming
    # runtime. Preserve its request contract while using the model's official
    # eager generation path on MPS/CPU.
    upstream.FastBreezeStreamingRuntime = _AppleSiliconBreezeRuntime
    upstream._settings = upstream.ApiSettings(  # noqa: SLF001 - pinned integration seam.
        model=args.model,
        fast_all=False,
        fast_text_encoder=False,
        fast_backbone_prefill=False,
        fast_backbone_decode=False,
        fast_depth_decoder=False,
        fast_codec=False,
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
