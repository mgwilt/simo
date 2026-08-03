---
type: Evidence Record
title: Runtime operations evidence
description: Records structured metrics, privacy sentinel, lifecycle, cancellation cleanup, and operator-contract evidence.
tags: [evidence, operations, metrics, privacy, shutdown, cancellation]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T01:14:24Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T01:14:24Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-E-006
  authority: evidence
  repository_paths: [README.md, python/simo/operations.py, python/simo/runtime.py, python/simo/cli.py, python/simo/adapters/pipecat, tests/python/test_operations.py, tests/python/test_cli.py, docs/operations/runtime-observability.md]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# E-006: Runtime operations

- Revision: `e5a6f6a408c3d544884ff87502091f7977b7d84b`.
- Environment: Mac Studio, Apple M3 Ultra, Python 3.13.7; deterministic Pipecat/Flecs execution without model weights.
- Method: ran the strict native build, 37 Python tests, documentation validation, five knowledge regression tests, whitespace checks, and Ruff lint/format checks on every changed Python file. Executed `simo headless` as a fresh subprocess with a privacy sentinel transcript, parsed every standard-error line as JSON, and inspected the result separately.
- Result: tests and execution prove a pure fixed-schema JSONL event stream, lifecycle and terminal metric events, world/queue/drop counters, stage calls/errors/durations, TTS first generated audio timing, exception-type-only failure events, normal cleanup, task-cancellation cleanup, terminal-interrupt status 130, and absence of sentinel transcript content from Simo operational events. The commit hook independently reran documentation, knowledge, and staged-whitespace gates.

Proves: the headless lifecycle and selected STT/text/TTS adapters share the aggregate metric contract; normal and cancelled paths exercised by tests release their owned pipeline/native resources; Simo's event API does not serialize content or exception messages.

Does not prove: live audio transport cleanup, third-party log privacy, speaker playback latency, live model timings, persistent metrics export, or cancellation during a non-yielding Metal operation.
