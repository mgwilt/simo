---
type: Evidence Record
title: Reproducible completion gates evidence
description: Records the locked native, runtime, type, lint, format, documentation, knowledge, and whitespace checks for the current Simo implementation.
tags: [evidence, quality, tests, typing, lint, okf, native]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T02:17:32Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T02:17:32Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-E-010
  authority: evidence
  repository_paths: [README.md, pyproject.toml, uv.lock, include/simo, src, python/simo, tests/python, scripts, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# E-010: Reproducible completion gates

- Revision: `8b1cb340cbfc962296dcdb87764986bb9ce8b9db`.
- Environment: Mac Studio, Apple M3 Ultra, Python 3.13.7, locked Ruff 0.12.11, locked Pyright 1.1.411, and the repository's frozen dependency environment.
- Method: rebuilt the native Flecs core; ran all first-party Python unit tests; ran Pyright against `python/simo`; ran Ruff lint and format checks across `python/simo`, `tests/python`, and `scripts`; validated the OKF bundle; ran the knowledge regression suite; and ran Git whitespace validation.
- Result: native build passed; 56 Python tests passed; Pyright reported zero errors and warnings; Ruff reported zero lint errors and all 49 first-party Python files formatted; 33 documentation concepts produced zero validation errors and the one existing context-size warning; five knowledge tests passed; whitespace validation passed.

Proves: the declared quality commands are installed from the lock, documented, executable, and green at the recorded revision; durable architecture and operations concepts carry current proof boundaries.

Does not prove: human conversation, microphone calibration, barge-in, subjective audio quality, behavior on another machine, dependency reproducibility after upstream sources disappear, or production deployment.
