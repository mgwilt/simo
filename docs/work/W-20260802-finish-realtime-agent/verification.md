---
type: Verification Record
title: Finish Simo verification
description: Records proportional checks for the complete realtime-agent product.
tags: [work, verification, product]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T02:17:32Z }
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
- `E-011` records partial `A-008` evidence at `ed30e7f`: application-controlled RMS calibration completed without retained audio; an energy-gated live run reached three STT calls and emitted interruption signals but was rejected by the user for VAD and latency quality; Silero then replaced the energy gate and its corrected probe evaluated `1626` neural windows from `2602` Arctis input chunks. The maximum confidence was `0.031398`, so no Silero turn was accepted at `0.5`. These runs prove device delivery, detector execution, privacy-safe counters, and clean teardown, not acceptable conversation quality.
- Human-accepted microphone turn boundaries, real playback interruption, cancellation during a Metal kernel, and three-turn live latency remain unverified. `A-008` and final publication record `A-011` remain open.
