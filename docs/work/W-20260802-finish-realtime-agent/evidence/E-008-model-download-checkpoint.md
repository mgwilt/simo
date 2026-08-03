---
type: Evidence Record
title: Model download checkpoint evidence
description: Records immutable model selection, exact transfer planning, explicit acceptance, completeness markers, and fail-closed preflight evidence.
tags: [evidence, macos, models, mlx, download, preflight]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T01:44:19Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T01:44:19Z }
sources:
  - id: qwen-tts-mlx
    resource: https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-6bit
    title: Qwen3-TTS 0.6B CustomVoice 6-bit MLX repository
  - id: parakeet-model
    resource: https://huggingface.co/mlx-community/parakeet-tdt-0.6b-v3
    title: Parakeet TDT 0.6B v3 MLX repository
  - id: qwen-text-mlx
    resource: https://huggingface.co/mlx-community/Qwen3.5-4B-4bit
    title: Qwen3.5 4B 4-bit MLX repository
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-E-008
  authority: evidence
  repository_paths: [README.md, python/simo/config.py, python/simo/doctor.py, scripts/setup_models.py, tests/python/test_config.py, tests/python/test_doctor.py, tests/python/test_setup_models.py]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# E-008: Model download checkpoint

- Revision: `3be0e3702d8b5bbd83d5689cedf69850b6d994e0`.
- Selected repositories: Qwen3-TTS at `7dc92af14613355896fcab13b268c19ede233139`, Parakeet at `ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15`, and Qwen3.5 at `0e7ffd5c629ef7719d4cbc04069232580bfa9d9c`.[^qwen-tts-mlx][^parakeet-model][^qwen-text-mlx]
- Plan: 7,403,765,096 bytes (6.90 GiB) expected transfer and 11,402,190,018 bytes (10.62 GiB) required free space, including 25 percent working allowance and 2 GiB minimum overhead.
- Method: ran the plan-only command, native build, 50 Python tests, documentation validation, five knowledge regression tests, changed-file Ruff lint/format checks, and whitespace validation. Tests use a fake repository downloader to exercise explicit acceptance, revision forwarding, required-file validation, idempotency, marker writing, and incomplete or mismatched preflight states without downloading weights.
- Result: the default setup command performs no network transfer. `--accept-download` is required to call the downloader; every call includes the full configured revision. Doctor remains not ready until required files exist and `.simo-model.json` atomically records the matching model ID and revision.

Proves: Simo has a bounded, reviewable, explicitly authorized installation path for the three selected model repositories, and incomplete or stale local state cannot satisfy live preflight.

Does not prove: successful transfer from Hugging Face, artifact byte-level integrity beyond repository revision selection, model loading, Metal execution, transcription, generation, speech synthesis, or live audio.

[^qwen-tts-mlx]: Qwen3-TTS 0.6B CustomVoice 6-bit MLX repository metadata, checked 2026-08-02 for pinned revision and file sizes.
[^parakeet-model]: Parakeet TDT 0.6B v3 MLX repository metadata, checked 2026-08-02 for pinned revision and file sizes.
[^qwen-text-mlx]: Qwen3.5 4B 4-bit MLX repository metadata, checked 2026-08-02 for pinned revision and file sizes.
