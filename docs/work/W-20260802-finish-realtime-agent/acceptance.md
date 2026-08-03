---
type: Work Acceptance
title: Reliable macOS voice-path acceptance
description: Defines executable evidence for Simo's reliable and responsive macOS voice path.
tags: [work, acceptance, product, evidence]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T02:53:48Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-ACCEPTANCE
  authority: coordination
  repository_paths: [python/simo, include/simo, src, tests, scripts, docs, pyproject.toml, uv.lock, lefthook.yml, .basedpyright-baseline.json]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# Acceptance

- [x] **A-001 — Reproducible macOS entrypoint:** A clean-checkout setup and `simo doctor`-style preflight truthfully report Apple hardware, models, and services, and a documented command starts headless mode. Proven by `E-001` at `800e5d0`.
- [x] **A-002 — End-to-end headless loop:** An executable acceptance test drives synthetic audio/transcript input through Pipecat, Flecs update, context snapshot injection, text inference, the replaceable TTS contract, audio frames, and clean shutdown. Proven by `E-002` at `6ea58b9`.
- [x] **A-003 — Context semantics:** Tests prove snapshot revision selection, bounded age/size, deterministic formatting, no live entity handles across the boundary, and context injection exactly once per inference turn. Proven by `E-002` at `6ea58b9`.
- [x] **A-004 — Observer/backpressure:** Tests prove transcript deduplication, queue overload policy, counters, non-blocking observer work, cancellation, and bounded failure propagation. Proven jointly by `E-002`, `E-005`, `E-007`, and `E-009`.
- [x] **A-005 — OKF knowledge graph:** The loader validates concepts, maps stable concept IDs and typed documentation edges into runtime entities, preserves source/freshness metadata, supports incremental refresh, and never treats graph presence as authorization or runtime attestation. Proven by `E-003` at `0a2b290`.
- [x] **A-006 — Open-source macOS inference:** Current primary evidence and executable adapter tests support the chosen local STT and text model/runtime on macOS; provider replacements do not change the core pipeline contract. Proven by `E-009` at `ad49653`.
- [x] **A-007 — Local macOS speech output:** Adapter tests cover PCM framing, errors, cancellation, and interruption; live evidence on the declared Mac proves actual open-source synthesis and records measured time-to-first-audio. Proven by `E-009` at `ad49653`.
- [x] **A-008 — Unattended realtime conversation:** On the declared Mac, synthetic audio completes at least three real Silero → STT → Flecs context → text → TTS turns, injects simulated playback echo without false turns, emits interruption signals, and captures latency and bounded-drop counters without human timing or participation. Proven by `E-012`.
- [x] **A-009 — Operations:** Structured logs/metrics expose queue depth/drops, world revision, inference and TTS timing, errors, lifecycle, and shutdown without logging raw private audio or transcript content by default. Proven jointly by `E-006`, `E-007`, and `E-009`.
- [x] **A-010 — Quality and knowledge:** Native/Python tests, lint/format/type checks, documentation validation, knowledge regression, build checks, and whitespace checks pass; durable architecture/interfaces/operations are promoted with proof limits. Proven by `E-010` at `8b1cb34`.
- [x] **A-011 — Publication record:** Every implementation milestone has conventional commits; closure records the local commit range and truthful no-publication reason. Proven by the terminal closure after `6907ee5`.
- [x] **A-012 — Strict static regression gates:** Ruff selects all rules with explicit project-policy exclusions, `ty` treats warnings as errors across runtime/tests/scripts, and BasedPyright strict rejects new `Any`/`Unknown` and other strict diagnostics across the same paths while preserving pre-existing debt in a reviewable baseline. Pre-commit runs every static gate; pre-push runs the native build, Python tests, documentation validation, and knowledge regression. Proven by `E-011` on the working tree based at `4672689`.
- [x] **A-013 — Synthetic Silero and echo gate:** The no-device proof generates speech with the pinned Qwen model, requires exactly three conditioned Silero utterances and interruption signals, replays the speech as simulated output echo, requires zero additional turns, and records aggregate confidence and suppression counters. Proven by `E-012`.
- [x] **A-014 — Bounded realtime response production:** Live text generation defaults to at most `48` tokens, and the selected TTS chunk interval is benchmarked on the pinned model before changing from `0.32` to `0.24` seconds. Proven by `E-012`; repeated p95 end-to-end latency remains follow-up evidence.
