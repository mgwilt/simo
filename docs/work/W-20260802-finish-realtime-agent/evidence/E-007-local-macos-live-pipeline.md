---
type: Evidence Record
title: Local macOS live pipeline evidence
description: Records local audio topology, worker lifecycle, interruption, device, PortAudio cleanup, and no-weights preflight evidence.
tags: [evidence, macos, audio, pipecat, interruption, pyaudio, mlx]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T01:35:05Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T01:35:05Z }
sources:
  - id: nltk-data-index
    resource: https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/index.xml
    title: NLTK data package index
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-E-007
  authority: evidence
  repository_paths: [README.md, pyproject.toml, uv.lock, python/simo/config.py, python/simo/doctor.py, python/simo/runtime.py, python/simo/adapters/pipecat/local_audio.py, scripts/setup_live_data.py, tests/python/test_live_runtime.py, tests/python/test_local_audio.py, tests/python/test_setup_live_data.py, docs/architecture/local-macos-voice-pipeline.md]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# E-007: Local macOS live pipeline

- Revision: `7f390b1325c48f7161294ef5a001b523e7b9428f`.
- Environment: Mac Studio, Apple M3 Ultra, 512 GB unified memory, PortAudio 19.7.0, PyAudio 0.2.14, Python 3.13.7, and pinned Pipecat `b114a367a32166207712e8a9c352215a6e24a0db`.
- Method: installed/locked PyAudio without model weights; installed NLTK `punkt_tab` from its official archive after matching published SHA-256 `e57f64187974277726a3417ca6f181ec5403676c717672eef6a748a7b20e0106`; ran the strict native build, 47 Python tests, documentation validation, five knowledge regression tests, whitespace checks, and changed-file Ruff lint/format checks. Outside the sandbox, ran JSON live preflight against the actual Mac.[^nltk-data-index]
- Result: tests prove typed device and VAD settings, bounded utterance/pre-roll behavior, interruption-frame emission, cancel/reset, sample-rate validation, full ordered local pipeline construction, real Pipecat worker setup/teardown with fake inference, normal/cancelled terminal metrics, preflight gating, and idempotent stream/executor/PyAudio release. Actual preflight passes platform, M3 Ultra, native core, all MLX/PyAudio modules, Metal, default Arctis Nova Pro input/output, and tokenizer checks; only the three model directories fail.

Proves: the no-weights live pipeline and its local resource boundaries are executable on the pinned stack; this Mac exposes suitable default audio devices to PortAudio outside the sandbox; live start is truthfully blocked before device access while weights are absent.

Does not prove: microphone capture, real STT/text/TTS execution, audible playback, voice quality, acoustic feedback behavior, user barge-in, three-turn context behavior, or live latency.

[^nltk-data-index]: NLTK data package index, checked 2026-08-02: `punkt_tab` archive URL, SHA-256, compressed size, and uncompressed size.
