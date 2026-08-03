---
type: Evidence Record
title: Qwen MLX TTS adapter evidence
description: Records no-weights streaming, PCM, cancellation, and Pipecat boundary evidence for Qwen3-TTS through MLX-Audio.
tags: [evidence, mlx, tts, pipecat, macos, cancellation]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:55:40Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:55:40Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-E-005
  authority: evidence
  repository_paths: [README.md, python/simo/config.py, python/simo/inference.py, python/simo/adapters/pipecat/qwen_tts.py, tests/python/test_config.py, tests/python/test_qwen_tts.py]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# E-005: Qwen MLX TTS adapter

- Revision: `f07a5e5a0f7f6bd5c456a56201cbf3fe4cbff6d1`.
- Environment: Mac Studio, Apple M3 Ultra, Python 3.13.7; MLX 0.32.0 and MLX-Audio 0.4.6 installed without model weights.
- Method: ran the strict native build, 32 Python tests, documentation validation, five knowledge regression tests, whitespace checks, and Ruff lint/format checks on every Python file changed by the revision. The commit hook independently reran documentation, knowledge, and staged-whitespace gates.
- Result: tests prove lazy single-load behavior, the selected built-in `Aiden` voice, streaming generation with a configurable positive interval, clipped little-endian signed 16-bit PCM, sample-rate and frame validation, mono contextual Pipecat audio frames, bounded cross-thread delivery, backend error framing, and cooperative producer shutdown when the async consumer closes.

Proves: the replaceable Qwen/MLX-Audio boundary and its Pipecat adapter execute deterministically with fake model results; queue capacity bounds generated chunks waiting to cross from the synthesis worker; interruption can stop delivery and generation between yielded model chunks.

Does not prove: model loading or synthesis with weights, voice quality, time-to-first-audio, sustained realtime throughput, speaker playback, microphone interaction, or cancellation while MLX-Audio is inside a non-yielding Metal operation.
