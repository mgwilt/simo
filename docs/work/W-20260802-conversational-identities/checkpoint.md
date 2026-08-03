---
type: Work Checkpoint
title: Conversational identities checkpoint
description: Captures the current resumable state for durable aliases, private memory, and the active WebRTC milestone.
tags: [work, checkpoint, aliases, memory, livekit]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T16:17:35Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-CHECKPOINT
  authority: coordination
  repository_paths: [docs/work/W-20260802-conversational-identities]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# Checkpoint

- Base revision: `fac700e8141808aa032ccc13c891c6be01af9595`.
- Dirty paths: documentation updates for this checkpoint and `E-006` only.
- Completed predecessor: `W-20260802-finish-realtime-agent` at `b6b3386`.
- Completed `T-001` at `c668277`: platform-default or overridden local data root, schema-versioned SQLite ownership, stable aliases, immutable persona/runtime-profile versions, private portable OKF bundles, safe bounded export/import, conversation identity, structured CLI, and explicit deletion.
- Completed `T-002` at `59a0c4e`: ordered attributed events, distinct generated/submitted/spoken assistant stages, transcript review/export/delete, and process-restart resumption.
- Completed `T-003` at `f43d110`: one isolated Flecs world per alias/conversation, typed participant graph identity, bounded immutable context snapshots, and fail-closed unknown speakers.
- Completed `T-004` at `ed89281` and `60ff5d0`: serialized private relationship learning, provenance and freshness, correction and forgetting, portable alias OKF materialization, Flecs memory projection, and restart recall.
- Historical `T-005` transport layer at `00033bd` and `5cc44b9`: room-scoped tokens, allow-listed audio-only subscriptions, remote SID preservation through Pipecat, a structured `simo lab prove-webrtc` command, and an observed two-process bidirectional WebRTC PCM exchange through self-hosted LiveKit 1.13.5 with zero self-echo or identity errors.
- Completed `T-005` at `a69c11e` through `6499101`: local STT/LLM/TTS providers, Silero and turn handling, bounded session-event persistence, RoomIO, isolated context snapshots, and a persisted alias runtime are owned directly by LiveKit Agents.
- Replacement `T-006` room proof at `6499101`: two independent OS processes and distinct LiveKit SIDs completed the real local-model audio loop with two spoken turns each, three remote synthetic-audio transcriptions, reviewable attributed transcripts, zero self-echo, unexpected identities, attribution errors, duplicate turns, or incomplete generated turns, and no raw audio retention. One spoken turn was interrupted; latency, barge-in rates, and held-out scenario floors remain open.
- Interactive headset slice at `fac700e`: `simo talk --alias …` starts one persisted LiveKit alias and one native PlatformAudio human participant. Live doctor passed on the declared M3 Ultra with default Arctis Nova Pro recording/playout; a bounded observed startup produced distinct participant SIDs and clean persistence/shutdown without raw audio. Human conversation quality remains operator evidence, not an automated acceptance claim.
- Verification: 108 Python tests, Ruff, format, `ty`, BasedPyright strict, and the LiveKit-native doctor pass. The two observed room runs retained text/timing and aggregate measurements but no raw audio.
- Architecture decision: `D-009` makes LiveKit Agents the sole realtime orchestrator and makes the Pipecat proof a predecessor baseline. No Pipecat path will be deleted until LiveKit Agents replacement tests and a live room run pass.
- Current milestone: `T-006` removes the predecessor Pipecat surface now that replacement unit, two-process room, and local-headset startup evidence exists.
- Blocker: none.
- Next action: delete Pipecat dependencies, adapters, legacy commands/tests, stale ownership claims, and the vendored submodule while retaining equivalent deterministic coverage on LiveKit-owned paths.
