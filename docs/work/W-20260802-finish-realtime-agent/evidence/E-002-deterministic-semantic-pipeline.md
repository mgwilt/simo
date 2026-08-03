---
type: Evidence Record
title: Deterministic semantic pipeline evidence
description: Records the no-model Pipecat-to-Flecs-to-inference-to-audio acceptance path and its causal observer correction.
tags: [evidence, pipecat, flecs, context, observer, headless]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:31:00Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:31:00Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-E-002
  authority: evidence
  repository_paths: [python/simo/adapters/pipecat, python/simo/observation.py, python/simo/runtime.py, tests/python]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# E-002: deterministic semantic pipeline

- Revision: `6ea58b9c0b2992dabebfc7a47ced5638f19500aa`.
- Environment: the `E-001` Mac and Python environment; vendored Pipecat `b114a367a32166207712e8a9c352215a6e24a0db`; native library rebuilt from the revision's sources.
- Method: ran the native build/test, 21 Python tests, documentation validation, five knowledge tests, and whitespace checks; ran `simo headless` with two final transcripts through Pipecat `Pipeline`, the shared semantic observer, bounded keyed mailbox, semantic turn processor, native Flecs engine, deterministic text provider, deterministic PCM TTS provider, and teardown.
- Result: all checks pass. The two-turn command reports two ordered world revisions, two context injections, two LLM text frames, two non-empty 24 kHz mono PCM TTS frames, two accepted observations, ten deduplicated repeated frame sightings, zero mailbox drops or leftovers, zero native drops, and two processed/retained semantic events.

An initial implementation allowed the asynchronous observer to enqueue turn 2 before turn 1's tick, producing one shared revision. The accepted implementation confines observer run-ahead to a bounded keyed mailbox and grants only the ordered semantic turn processor authority to promote the matching event into Flecs.

Proves: `A-002`; `A-003`; observer sightings do not duplicate semantic ingress; observer run-ahead cannot contaminate earlier turn context; bounded mailbox drop policy is executable.

Does not prove: live STT/LLM/TTS, acoustic audio validity or quality, realtime latency, slow-provider interruption/cancellation, arbitrary concurrent schedules, production load, microphone/speaker transport, or the remaining `A-004` failure-propagation and cancellation cases.
