---
type: Verification Record
title: Finish Simo verification
description: Records proportional checks for the complete realtime-agent product.
tags: [work, verification, product]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T01:44:19Z }
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
- Model-weight execution, microphone capture, speaker playback, cancellation during a Metal kernel, live latency, and live operational readiness remain unverified. `A-006`, `A-007`, `A-008`, and `A-009` remain open pending live execution; `A-004` remains open until real playback interruption is observed.
