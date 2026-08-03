---
type: Evidence Record
title: MLX STT and text adapter evidence
description: Records package, Metal, API, and no-weights adapter evidence for Parakeet and Qwen text inference.
tags: [evidence, mlx, stt, llm, macos]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:47:24Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:47:24Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-E-004
  authority: evidence
  repository_paths: [pyproject.toml, uv.lock, python/simo/inference.py, python/simo/adapters/pipecat/inference.py, tests/python/test_inference.py]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# E-004: MLX STT and text adapters

- Revision: `754265a9879d53ca9d5e26447dba39a7aab18512`.
- Environment: Mac Studio, Apple M3 Ultra, Python 3.13.7; MLX 0.32.0, MLX-Audio 0.4.6, Parakeet-MLX 0.5.2, and MLX-LM 0.31.3.
- Method: installed locked optional inference packages without weights; outside the managed sandbox imported `mlx.core`, `parakeet_mlx.from_pretrained`, and `mlx_lm.load/generate`; ran the strict native build, 28 Python tests, documentation/knowledge validation, and whitespace checks.
- Result: Metal is available outside the sandbox and all selected runtime APIs load. Tests prove lazy single-load behavior, signed 16-bit PCM normalization, Parakeet streaming-session use, sample-rate/error bounds, MLX-LM token bounds, single context-block prompt injection, final Pipecat transcription emission, and LLM response frame emission. No model directory or weight was downloaded.

Proves: selected packages and public entrypoints are compatible with this Mac/Python environment; replaceable STT/text contracts and Pipecat processors execute with fake model backends.

Does not prove: `A-006` model execution, transcription/generation quality, realtime latency, memory use with weights, multilingual behavior, cancellation during Metal kernels, or live audio.
