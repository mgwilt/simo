---
type: Work Acceptance
title: Finished Simo acceptance
description: Defines the executable and live evidence required to complete the Simo realtime-agent product goal.
tags: [work, acceptance, product, evidence]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:31:00Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-ACCEPTANCE
  authority: coordination
  repository_paths: [python/simo, include/simo, src, tests, scripts, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# Acceptance

- [x] **A-001 — Reproducible macOS entrypoint:** A clean-checkout setup and `simo doctor`-style preflight truthfully report Apple hardware, models, and services, and a documented command starts headless mode. Proven by `E-001` at `800e5d0`.
- [x] **A-002 — End-to-end headless loop:** An executable acceptance test drives synthetic audio/transcript input through Pipecat, Flecs update, context snapshot injection, text inference, the replaceable TTS contract, audio frames, and clean shutdown. Proven by `E-002` at `6ea58b9`.
- [x] **A-003 — Context semantics:** Tests prove snapshot revision selection, bounded age/size, deterministic formatting, no live entity handles across the boundary, and context injection exactly once per inference turn. Proven by `E-002` at `6ea58b9`.
- [ ] **A-004 — Observer/backpressure:** Tests prove transcript deduplication, queue overload policy, counters, non-blocking observer work, cancellation, and bounded failure propagation.
- [ ] **A-005 — OKF knowledge graph:** The loader validates concepts, maps stable concept IDs and typed documentation edges into runtime entities, preserves source/freshness metadata, supports incremental refresh, and never treats graph presence as authorization or runtime attestation.
- [ ] **A-006 — Open-source macOS inference:** Current primary evidence and executable adapter tests support the chosen local STT and text model/runtime on macOS; provider replacements do not change the core pipeline contract.
- [ ] **A-007 — Local macOS speech output:** Adapter tests cover PCM framing, errors, cancellation, and interruption; live evidence on the declared Mac proves actual open-source synthesis and records measured time-to-first-audio.
- [ ] **A-008 — Live macOS conversation:** On the declared Mac, a human can speak, receive a context-informed spoken response, interrupt it, and complete at least three turns while metrics and bounded-drop counters are captured.
- [ ] **A-009 — Operations:** Structured logs/metrics expose queue depth/drops, world revision, inference and TTS timing, errors, lifecycle, and shutdown without logging raw private audio or transcript content by default.
- [ ] **A-010 — Quality and knowledge:** Native/Python tests, lint/format/type checks, documentation validation, knowledge regression, build checks, and whitespace checks pass; durable architecture/interfaces/operations are promoted with proof limits.
- [ ] **A-011 — Publication record:** Every implementation milestone has conventional commits; closure records commit/PR references or a truthful no-publication reason and leaves the repository clean.
