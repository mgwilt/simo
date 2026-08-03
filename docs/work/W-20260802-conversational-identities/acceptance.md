---
type: Work Acceptance
title: Conversational identities acceptance
description: Defines executable evidence for durable aliases, multi-turn history, learning, WebRTC pairing, and autonomous improvement.
tags: [work, acceptance, aliases, conversation, livekit, evaluation]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T16:17:35Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-ACCEPTANCE
  authority: coordination
  repository_paths: [python/simo, include/simo, src, tests, scripts, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# Acceptance

- [x] **A-001 — Alias persistence:** Stable aliases, persona versions, runtime profiles, active pointers, and private OKF roots survive restart and support lossless export/import. Proven by `E-001` at `c668277`.
- [x] **A-002 — Conversation history:** An indexed local store persists ordered participant-attributed events, final user text, generated/submitted/spoken assistant stages, interruption state, timing, and version references. Proven by `E-002` at `59a0c4e`.
- [x] **A-003 — Structured CLI:** Alias and conversation create/list/show/export/delete/resume commands have human-readable and JSON contracts with deterministic tests. Proven by `E-001` and `E-002` at `c668277` and `59a0c4e`.
- [x] **A-004 — Twenty-turn continuity:** Synthetic acceptance resumes a persisted twenty-turn conversation after restart and recalls both an early fact and a later correction without cross-conversation contamination. Proven by `E-003` and `E-004` at `f43d110` and `60ff5d0`.
- [x] **A-005 — Live semantic isolation:** Each active alias/conversation owns an isolated Flecs projection; bounded snapshots expose stable participant and conversation identity without storage or entity handles crossing the Pipecat boundary. Proven by `E-003` at `f43d110`.
- [x] **A-006 — Safe relationship learning:** Low-risk direct claims auto-promote with provenance and freshness; corrections supersede without erasing history; prohibited classes and permission changes fail closed; inspect/correct/forget survive restart. Proven by `E-004` at `ed89281` and `60ff5d0`.
- [x] **A-007 — Transcript privacy:** Text and timing retention are explicit, operational telemetry remains content-free, raw audio defaults off, and deletion removes the requested conversation and derived private memories according to declared policy. Proven by `E-002` and `E-004` at `59a0c4e`, `ed89281`, and `60ff5d0`.
- [x] **A-008 — LiveKit pairing:** Two independent Simo processes join one self-hosted LiveKit room, publish speech, subscribe only to remote audio, preserve attribution, and complete a real TTS-to-WebRTC-to-VAD-to-STT-to-Flecs loop. Proven by `E-006` at `6499101`.
- [ ] **A-009 — Held-out room suite:** Ten held-out scenarios across three seeds finish without self-echo turns, duplicates, attribution errors, crashes, or deadlocks.
- [ ] **A-010 — Mechanics targets:** On the declared Mac, synthetic ground truth proves speech onset within 200 ms, endpoint within 600 ms, at least 95% barge-in detection, fewer than one false start per ten minutes of background audio, and p95 end-of-speech to first response audio at or below 1.5 seconds.
- [ ] **A-011 — Autonomous improvement:** A deliberately inferior candidate is rejected; a candidate with at least 5% material improvement, 95% bootstrap confidence, and no hard-floor regression auto-promotes; a failing canary automatically rolls back.
- [ ] **A-012 — Evolving distinct personas:** Persona/runtime changes are versioned and diffable, stable alias identity and policy remain unchanged, and evaluation rejects convergence into indistinguishable aliases.
- [ ] **A-013 — Reproducible quality:** Native/Python tests, strict static gates, documentation validation, knowledge regression, synthetic proofs, and privacy checks pass from pinned dependencies without human participation.
- [ ] **A-014 — Publication:** Each bounded milestone has a conventional commit; closure records immutable references or a truthful no-publication reason and leaves no unexplained repository changes.
- [ ] **A-015 — Single realtime owner:** LiveKit Agents owns room I/O, VAD, turn state, interruption, STT/LLM/TTS scheduling, and session events; Simo retains Flecs, persistence, knowledge, policy, and evaluation; no Pipecat runtime dependency, adapter, submodule, or current architecture claim remains after replacement evidence passes.

`E-005` is historical predecessor evidence for the underlying transport. `E-006` supersedes it for `A-008` with the replacement LiveKit Agents model loop. Neither closes `A-015`, which additionally requires complete Pipecat removal.
