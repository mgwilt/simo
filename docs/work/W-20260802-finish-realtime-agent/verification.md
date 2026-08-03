---
type: Verification Record
title: Finish Simo verification
description: Records proportional checks for the complete realtime-agent product.
tags: [work, verification, product]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T02:53:48Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-VERIFICATION
  authority: evidence
  repository_paths: [include/simo, src, python/simo, tests, scripts, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# Verification

- `E-001` verifies `A-001` at `800e5d0`: native build/test, package installation, Mac hardware preflight, deterministic headless execution, full Python tests, and truthful missing-live-prerequisite reporting.
- `E-002` verifies `A-002` and `A-003` at `6ea58b9`: a real Pipecat pipeline advances Flecs once per ordered turn, injects immutable bounded/fresh snapshots, produces deterministic LLM text and PCM TTS frames, and shuts down cleanly.
- `E-003` verifies `A-005` at `0a2b290`: validated concepts and internal links project into the private Flecs graph; incremental refresh updates/removes entities; invalid bundles cannot mutate the graph.
- `E-004` records partial `A-006` evidence at `754265a`: package versions resolve, Metal and public APIs load outside the sandbox, and lazy STT/text boundaries pass fake-backend tests without weights.
- `E-005` records partial `A-004` and `A-007` evidence at `f07a5e5`: fake-backend Qwen streaming crosses a bounded worker queue into validated mono PCM Pipecat frames; consumer close cooperatively stops generation between chunks and backend failures become bounded error frames.
- `E-006` records partial `A-009` and `A-010` evidence at `e5a6f6a`: the headless owner and selected live inference adapters share a pure fixed-schema JSONL stream and aggregate metrics; normal and cancelled lifecycles clean up; terminal interrupt returns status 130; privacy sentinel content is absent from operational events.
- `E-007` records partial `A-004`, `A-008`, and `A-009` evidence at `7f390b1`: the local 16/24 kHz Pipecat topology executes worker setup/teardown with fake inference; energy turn detection emits interruption and bounded utterance frames; PortAudio ownership is explicit; outside-sandbox preflight sees MLX Metal and the actual default Mac audio devices.
- `E-008` records the model-download checkpoint at `3be0e37`: the installer is plan-only without explicit acceptance, resolves three immutable repository revisions totaling 6.90 GiB, reserves 10.62 GiB, verifies required files before writing atomic completion markers, and keeps doctor closed for incomplete or mismatched models.
- `E-009` verifies `A-006` and `A-007` at `ad49653`: immutable model markers pass doctor; real Qwen text, Qwen TTS, and Parakeet STT execute on MLX Metal; synthetic speech round-trips exactly; the same providers complete one Pipecat/Flecs semantic turn with zero errors or drops; and generated PCM plays through default PortAudio output.
- `E-010` verifies `A-010` at `8b1cb34`: the native build, 56 Python tests, first-party runtime Pyright, first-party Ruff lint/format, documentation validation, five knowledge tests, and whitespace validation all pass from the locked environment. Together `E-002`, `E-005`, `E-007`, and `E-009` satisfy `A-004`; `E-006`, `E-007`, and `E-009` satisfy `A-009`.
- `E-011` verifies `A-012` on the working tree based at `4672689`: the installed pre-commit launcher invokes Lefthook, the explicit all-files route passes frozen Ruff `ALL` lint and formatting, `ty` with warning failure, and baseline-ratcheted BasedPyright strict, and the installed pre-push launcher passes the native build, 61 Python tests, documentation validation, and five knowledge tests. Managed `.git` permissions blocked replacement of the existing launcher files, not invocation.
- `E-012` verifies `A-008`, `A-013`, and `A-014`: application-controlled measurement established ambient/speech Silero separation after DC removal and bounded gain; the unattended real-model proof detected three generated utterances and emitted three interruption signals, suppressed all `84` simulated playback-echo chunks with zero false turns, reproduced the exact STT phrase across three Pipecat/Flecs context injections, advanced world revision to `3`, and reported zero mailbox drops. Isolated pinned-model measurement selected the bounded realtime response and TTS interval.
- Cancellation during an in-flight Metal kernel and repeated per-turn p95 latency remain unverified. Final publication record `A-011` remains open. Subjective headset and room quality are explicitly outside synthetic attestation.
