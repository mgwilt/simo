---
type: Evidence Record
title: macOS entrypoint and preflight evidence
description: Records native build, packaged command, headless lifecycle, and truthful live-preflight results on the target Mac.
tags: [evidence, macos, preflight, headless, native]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:20:54Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:20:54Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-E-001
  authority: evidence
  repository_paths: [README.md, pyproject.toml, python/simo, scripts/build_native.py, tests/python]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# E-001: macOS entrypoint and preflight

- Revision: `800e5d0071c98ced4a2e47bc05998ecbdf6af51e`.
- Environment: macOS Darwin 25.5.0; Mac Studio `Mac15,14`; Apple M3 Ultra; 512 GB unified memory; Apple Clang 21; Python 3.13.7.
- Method: resolved and installed the locked runtime in the repository-local environment; built Flecs and both first-party native translation units with the macOS system compiler using C17/C++20 and strict warnings; linked the dylib and native test; ran the native test, 18 Python tests, documentation validation, five knowledge-validation tests, whitespace checks, headless preflight, deterministic two-transcript execution, and live preflight.
- Result: native and Python tests pass; the installed `simo` command auto-discovers `.build/simo/libsimo_core.dylib`; headless preflight reports the exact target hardware and `ready: true`; headless execution returns revision 1 with both ordered transcript items, two processed events, no drops, and clean shutdown. Live preflight returns `not ready` and enumerates the three absent MLX runtimes, Pipecat sentence data, and three absent model directories. No model weights were downloaded.

Proves: `A-001` on the tested Mac; typed no-weights configuration; truthful headless/live prerequisite separation; system-compiler native build and test; deterministic native lifecycle through the packaged command.

Does not prove: the Pipecat inference pipeline, live MLX compatibility, model quality or latency, microphone/speaker behavior, interruption, OKF graph projection, non-macOS support, or a fresh external clone. `A-009` remains open because structured operational telemetry and privacy behavior need later runtime evidence.
