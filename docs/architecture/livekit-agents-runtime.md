---
type: Architecture Concept
title: LiveKit Agents runtime
description: Defines Simo's implemented LiveKit Agents orchestration plane and the remaining evidence-gated removal of Pipecat.
tags: [architecture, livekit, agents, voice, flecs, migration]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T16:17:35Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T16:17:35Z }
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
  - id: simo-livekit-runtime
    resource: ../../python/simo/livekit_runtime.py
    title: Persisted Simo LiveKit Agents runtime
  - id: simo-livekit-talk
    resource: ../../python/simo/livekit_local_talk.py
    title: Simo native LiveKit headset participant
  - id: simo-livekit-lab
    resource: ../../python/simo/livekit_agent_lab.py
    title: Simo two-process LiveKit Agents conversation lab
simo:
  profile_version: 1
  stable_id: DOC-0006
  authority: architecture
  repository_paths: [pyproject.toml, uv.lock, python/simo, tests/python, docs]
  owner: codex/gpt-5.6-sol
---
# LiveKit Agents runtime

## Decision and current truth

Simo uses self-hosted LiveKit Server plus local LiveKit Agents sessions as its realtime orchestration plane. LiveKit Agents supports cascaded STT-LLM-TTS, realtime speech-to-speech, and half-cascade pipelines; Simo currently uses the cascaded local-model path because it exposes the clearest attribution, transcript, context, and evaluation boundaries.[^livekit-pipelines]

The implemented path now adapts local Parakeet STT, MLX text generation, Qwen TTS, Silero VAD, Flecs snapshots, and persisted session events directly to LiveKit Agents. `simo talk --alias …` starts one alias plus a native LiveKit `PlatformAudio` headset participant; `simo lab converse` starts two aliases as separate OS processes and permits communication only through room audio.[^simo-livekit-runtime][^simo-livekit-talk][^simo-livekit-lab]

Pipecat remains in the repository only as a predecessor implementation and deterministic migration fallback. It is not part of the interactive `simo talk` or two-alias `simo lab converse` path. This concept remains draft until Pipecat code, dependency, tests, submodule, and obsolete current-tense claims are removed without reducing coverage.

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

For local human conversation, a second RTC participant uses LiveKit's native platform audio device module. WebRTC echo cancellation, noise suppression, and automatic gain control are enabled; the human publishes only a microphone-source track and subscribes only to the declared alias identity. The local server and both participants receive fresh room-scoped identities for each invocation.[^simo-livekit-talk]

## Migration and removal gate

The first four removal gates now have replacement evidence at `6499101` and `fac700e`. Final removal still requires:

1. deterministic provider and session-event tests for local STT, text, TTS, Flecs injection, transcript stages, cancellation, and shutdown;
2. an observed self-hosted two-process run through TTS, WebRTC, Silero, STT, Flecs, and the next response;
3. zero self-echo or unexpected participant attribution in that run;
4. replacement documentation and operations evidence;
5. deletion of the Pipecat dependency, adapter tree, tests that only attest Pipecat, current ownership claims, and the vendored submodule without reducing native, persistence, privacy, or model coverage.

The observed LiveKit Agents two-process run now replaces the earlier Pipecat/LiveKit run for target-pipeline evidence. The earlier record remains historical transport evidence. Documentation validation alone cannot satisfy the remaining removal gate.

[^livekit-pipelines]: LiveKit Agents voice pipeline types, verified 2026-08-03.
[^livekit-nodes]: LiveKit Agents pipeline nodes and hooks, verified 2026-08-03.
[^livekit-turns]: LiveKit Agents turn handling and tuning, verified 2026-08-03.
[^livekit-room-io]: LiveKit Agents `RoomIO` source on the mutable `main` branch, inspected 2026-08-03; refresh by `stale_after` before relying on API details.
[^simo-livekit-runtime]: `python/simo/livekit_runtime.py`, `python/simo/adapters/livekit`, and focused tests at revisions `24a7420` through `6499101`.
[^simo-livekit-talk]: `python/simo/livekit_local_talk.py`, `python/simo/livekit_local_server.py`, `python/simo/cli.py`, `python/simo/doctor.py`, and focused tests at revision `fac700e`.
[^simo-livekit-lab]: `python/simo/livekit_agent_lab.py` and `tests/python/test_livekit_agent_lab.py` at revision `6499101`; observed room evidence is recorded in `W-20260802-conversational-identities#E-006`.
