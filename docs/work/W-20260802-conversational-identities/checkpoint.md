---
type: Work Checkpoint
title: Conversational identities checkpoint
description: Captures the current resumable state for durable aliases, private memory, and the active WebRTC milestone.
tags: [work, checkpoint, aliases, memory, livekit]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T05:37:38Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-CHECKPOINT
  authority: coordination
  repository_paths: [docs/work/W-20260802-conversational-identities]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# Checkpoint

- Base revision: `b6b33863479de06f3b6a94ca08b9c5fa86172d66`.
- Dirty paths at activation: none.
- Completed predecessor: `W-20260802-finish-realtime-agent` at `b6b3386`.
- Completed `T-001` at `c668277`: platform-default or overridden local data root, schema-versioned SQLite ownership, stable aliases, immutable persona/runtime-profile versions, private portable OKF bundles, safe bounded export/import, conversation identity, structured CLI, and explicit deletion.
- Completed `T-002` at `59a0c4e`: ordered attributed events, distinct generated/submitted/spoken assistant stages, transcript review/export/delete, and process-restart resumption.
- Completed `T-003` at `f43d110`: one isolated Flecs world per alias/conversation, typed participant graph identity, bounded immutable context snapshots, and fail-closed unknown speakers.
- Completed `T-004` at `ed89281` and `60ff5d0`: serialized private relationship learning, provenance and freshness, correction and forgetting, portable alias OKF materialization, Flecs memory projection, and restart recall.
- Historical `T-005` transport layer at `00033bd` and `5cc44b9`: room-scoped tokens, allow-listed audio-only subscriptions, remote SID preservation through Pipecat, a structured `simo lab prove-webrtc` command, and an observed two-process bidirectional WebRTC PCM exchange through self-hosted LiveKit 1.13.5 with zero self-echo or identity errors.
- Verification: repository pre-commit and pre-push contracts passed with 91 Python tests, native build/tests, Ruff, `ty`, BasedPyright strict, documentation validation, and five knowledge tests. The live probe passed outside the sandbox and retained aggregate measurements only.
- Architecture decision: `D-009` makes LiveKit Agents the sole realtime orchestrator and makes the Pipecat proof a predecessor baseline. No Pipecat path will be deleted until LiveKit Agents replacement tests and a live room run pass.
- Current milestone: `T-005` migrates local providers, Flecs context injection, persistence observers, RoomIO, Silero, and turn handling to LiveKit Agents.
- Blocker: none.
- Next action: pin LiveKit Agents and its Silero plugin, implement local STT/LLM/TTS and Simo context/event adapters, and pass deterministic replacement tests before rewriting the two-process room proof.
