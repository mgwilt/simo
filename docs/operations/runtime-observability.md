---
type: Operations Concept
title: Runtime observability and shutdown
description: Defines Simo's implemented privacy-safe event schema, aggregate runtime metrics, and bounded shutdown behavior.
tags: [operations, observability, privacy, lifecycle, metrics, shutdown]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T01:14:24Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T01:14:24Z }
sources:
  - id: operations-implementation
    resource: ../../python/simo/operations.py
    title: Simo operational metrics and event implementation
  - id: runtime-implementation
    resource: ../../python/simo/runtime.py
    title: Simo runtime lifecycle owner
  - id: operations-tests
    resource: ../../tests/python/test_operations.py
    title: Simo operational behavior tests
simo:
  profile_version: 1
  stable_id: DOC-0004
  authority: operations
  repository_paths: [README.md, python/simo/operations.py, python/simo/runtime.py, python/simo/cli.py, python/simo/adapters/pipecat, tests/python]
  owner: unassigned
---
# Runtime observability and shutdown

## Ownership and streams

`RuntimeMetrics` owns one process-local aggregate snapshot. Pipecat STT, text-inference, and Qwen TTS adapters receive it as an optional value boundary; it is deliberately separate from Pipecat's internal processor metrics. `HeadlessRuntime` owns lifecycle transitions and publishes a terminal snapshot.[^operations-implementation][^runtime-implementation]

The CLI writes the requested headless result to standard output. It writes operational events to standard error as newline-delimited JSON with schema `simo.event.v1`. Operators can therefore route machine results and telemetry independently. The headless result contains the synthetic transcripts explicitly supplied to the command; it is not a privacy-safe log channel.

## Event and metric contract

Operational events have an event name, UTC timestamp, mode, and fixed event-specific fields:

- `lifecycle`: `phase` and optional shutdown `reason`;
- `failure`: stage and exception type, never the exception message;
- `metrics`: the terminal aggregate runtime snapshot.

The aggregate snapshot reports lifecycle phase, shutdown reason, clean-shutdown flag, uptime, total errors, Flecs world revision, context queue depth/drop/accepted/processed/retained counters, observer mailbox depth/drop counters, and per-stage calls, errors, total/last duration, and first-output duration. Stages are knowledge projection, complete pipeline, STT, text inference, and TTS.[^operations-implementation]

TTS first output measures elapsed time until the adapter receives its first valid generated PCM chunk. It is not speaker playback latency. Durations are monotonic process-local wall time, not performance guarantees.

## Privacy boundary

The event API has no field for transcript text, prompt text, generated text, audio, model output, or exception messages. Failure events serialize only the exception class name. Tests pass a sentinel private transcript through normal and cancelled lifecycles and demonstrate that it is absent from emitted events.[^operations-tests]

This boundary does not sanitize Pipecat, ML runtime, operating-system, or future adapter logs. New logging integrations must be reviewed independently before sharing logs that may contain private inputs.

## Shutdown

Normal completion and task cancellation unwind the Pipecat pipeline and native Flecs owner before the terminal lifecycle event. Cancellation is recorded as a clean shutdown with reason `cancelled`; a terminal interrupt returns status `130`. Qwen synthesis cancellation stops delivery and cooperatively stops its worker between yielded chunks, but cannot preempt an in-flight Metal operation.[^runtime-implementation][^operations-tests]

## Evidence boundary

Revision `e5a6f6a408c3d544884ff87502091f7977b7d84b` passes the native build, 37 Python tests, documentation and knowledge validation, changed-file Ruff lint/format checks, and whitespace validation. This proves the headless lifecycle, pure JSONL event stream, aggregate metric contract, selected adapter instrumentation, privacy sentinel cases, cancellation cleanup, and interrupt exit behavior exercised by those tests.

It does not prove live microphone/speaker cleanup, external log-sink privacy, persistent metric export, signal behavior under every macOS process state, live model latency, or cancellation inside a non-yielding Metal kernel. A-009 remains open until the live transport is wired and exercised.

[^operations-implementation]: `python/simo/operations.py` and the instrumented Pipecat adapters at revision `e5a6f6a408c3d544884ff87502091f7977b7d84b`.
[^runtime-implementation]: `python/simo/runtime.py` and `python/simo/cli.py` at revision `e5a6f6a408c3d544884ff87502091f7977b7d84b`.
[^operations-tests]: `tests/python/test_operations.py`, `tests/python/test_cli.py`, `tests/python/test_inference.py`, and `tests/python/test_qwen_tts.py` at revision `e5a6f6a408c3d544884ff87502091f7977b7d84b`.
