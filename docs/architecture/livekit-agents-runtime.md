---
type: Architecture Proposal
title: LiveKit Agents runtime
description: Defines Simo's accepted target for one self-hosted realtime orchestrator and the evidence-gated migration from Pipecat.
tags: [architecture, livekit, agents, voice, flecs, migration]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T05:37:38Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T05:37:38Z }
stale_after: 2026-09-03
sources:
  - id: livekit-pipelines
    resource: https://docs.livekit.io/agents/models/pipelines/
    title: LiveKit Agents voice pipeline types
  - id: livekit-nodes
    resource: https://docs.livekit.io/agents/logic/nodes/
    title: LiveKit Agents pipeline nodes and hooks
  - id: livekit-turns
    resource: https://docs.livekit.io/agents/logic/turns/tuning/
    title: LiveKit Agents turn handling and tuning
  - id: livekit-room-io
    resource: https://github.com/livekit/agents/blob/main/livekit-agents/livekit/agents/voice/room_io/room_io.py
    title: LiveKit Agents RoomIO implementation
simo:
  profile_version: 1
  stable_id: DOC-0006
  authority: proposal
  repository_paths: [pyproject.toml, uv.lock, python/simo, tests/python, docs]
  owner: codex/gpt-5.6-sol
---
# LiveKit Agents runtime

## Decision and current truth

Simo will use self-hosted LiveKit Server plus a local LiveKit Agents worker as its sole realtime orchestration plane. LiveKit Agents supports cascaded STT-LLM-TTS, realtime speech-to-speech, and half-cascade pipelines; Simo initially retains the cascaded local-model path because it exposes the clearest attribution, transcript, context, and evaluation boundaries.[^livekit-pipelines]

This concept is an accepted target, not yet implemented authority. The current repository still executes Pipecat pipelines and the first two-process LiveKit proof used a Simo-owned Pipecat transport. Migration work is tracked by `W-20260802-conversational-identities`; this concept becomes stable architecture only after replacement tests, a full live-room model loop, and Pipecat removal.

## Ownership

| Owner | Responsibility |
|---|---|
| LiveKit Server | Self-hosted rooms, WebRTC signaling and media, remote participants, and transport identities |
| LiveKit Agents | RoomIO, audio input/output, VAD, endpointing, interruption, turn state, model scheduling, synchronized speech/transcription events, and session lifecycle |
| Flecs | One isolated live semantic world per active alias/conversation and bounded immutable context snapshots |
| SQLite | Transactional aliases, conversations, ordered events, experiments, evaluations, promotions, and rollback history |
| Alias OKF bundle | Durable private persona and perspective-bound learned knowledge |
| Simo policy layer | Permissions, retention, memory safety, evaluation floors, budgets, and promotion authority |

LiveKit Agents pipeline nodes can be overridden for custom audio preprocessing and STT, LLM, or TTS behavior, which is the intended seam for Simo's local Parakeet, MLX text, Qwen/Gepard-compatible TTS, and bounded Flecs context injection.[^livekit-nodes] Turn handling exposes endpointing, interruption, and preemptive-generation controls; runtime profiles version those tuneable values without allowing the optimizer to change code or policy.[^livekit-turns]

RoomIO creates participant audio input and output, attaches them to an `AgentSession`, and listens for participant, connection, transcript, state, and close events.[^livekit-room-io] Simo subscribes those events through bounded first-party sinks: the hot path records only immutable values and aggregate timing, while serialized owners perform SQLite and OKF writes outside callbacks.

## Session flow

```text
remote participant audio
  -> LiveKit RoomIO
  -> Silero and LiveKit turn handling
  -> local Parakeet STT
  -> attributed final transcript event
  -> bounded Simo event sink
  -> Flecs tick and immutable ContextSnapshot
  -> local text generation with persona and context
  -> local Qwen or compatible TTS
  -> synchronized actually-spoken event
  -> LiveKit remote audio output
```

Each active `(alias, conversation)` owns its `AgentSession`, Flecs world, participant mapping, and bounded event sink. Aliases never receive another alias's files, database handles, Flecs world, hidden scenario state, or generated transcripts. A two-alias lab joins two independent workers to one room and communicates only through remote audio.

## Migration and removal gate

Pipecat remains temporarily as a working predecessor while LiveKit Agents adapters are implemented. Removal requires:

1. deterministic provider and session-event tests for local STT, text, TTS, Flecs injection, transcript stages, cancellation, and shutdown;
2. an observed self-hosted two-process run through TTS, WebRTC, Silero, STT, Flecs, and the next response;
3. zero self-echo or unexpected participant attribution in that run;
4. replacement documentation and operations evidence;
5. deletion of the Pipecat dependency, adapter tree, tests that only attest Pipecat, current ownership claims, and the vendored submodule without reducing native, persistence, privacy, or model coverage.

The earlier Pipecat/LiveKit run is historical transport evidence, not proof that the target pipeline works. Documentation validation alone cannot satisfy any removal gate.

[^livekit-pipelines]: LiveKit Agents voice pipeline types, verified 2026-08-03.
[^livekit-nodes]: LiveKit Agents pipeline nodes and hooks, verified 2026-08-03.
[^livekit-turns]: LiveKit Agents turn handling and tuning, verified 2026-08-03.
[^livekit-room-io]: LiveKit Agents `RoomIO` source on the mutable `main` branch, inspected 2026-08-03; refresh by `stale_after` before relying on API details.
