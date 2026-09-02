---
type: Verification Record
title: Conversational identities verification
description: Records proportional checks for alias persistence, conversation behavior, learning, WebRTC rooms, and autonomous improvement.
tags: [work, verification, aliases, conversation, livekit]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-09-02T14:25:21Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-VERIFICATION
  authority: evidence
  repository_paths: [python/simo, include/simo, src, tests, scripts, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# Verification

`E-001` verifies `A-001` at `c668277`: stable alias UUIDs, manifests, persona/runtime-profile version lineages, active pointers, private OKF roots, process-restart reopening, safe bounded export/import, and foundational alias/conversation CLI all execute from the versioned local store.

`E-002` verifies `A-002` and `A-003` at `59a0c4e`: ordered attributed event history, speech-stage truth, restart resumption, primary transcript review, JSON export, and deletion execute from SQLite and the structured CLI.

`E-003` verifies `A-005` at `f43d110`: two active conversation-scoped Flecs worlds remain isolated and expose participant identity only through bounded immutable values.

`E-004` verifies `A-004`, `A-006`, and `A-007` at `ed89281` and `60ff5d0`: private learning, correction, provenance, OKF materialization, Flecs recall, restart continuity, forgetting, and conversation-derived deletion execute without changing permission or persona authority.

`E-005` historically supported the transport portion of `A-008` at `00033bd` and `5cc44b9` through the former Pipecat adapter. It remains a migration baseline, not current target-architecture evidence; `E-006` supplies the replacement loop.

`E-006` verifies `A-008` at `6499101`: two distinct Simo processes with private stores and personas joined one self-hosted room, ran local Qwen TTS through WebRTC, remote-only audio subscription, Silero, Parakeet, Flecs context, and local Qwen text generation, and persisted attributed review transcripts with no identity, self-echo, duplicate, incomplete-generation, or raw-audio failures. The local headset startup slice at `fac700e` additionally verifies native PlatformAudio device selection and a distinct human participant, but does not claim human conversational quality.

`E-007` verifies `A-016` from Simo implementation `c037f5f` and owned fork `a38d7d1`: the pinned Breeze source and model load on PyTorch MPS, report exact health metadata, and produce 24 kHz PCM through the Simo service contract. The fork itself passes 31 tests; one uncached fork-native request returned 23,040 PCM bytes. Its full benchmark records p95 first audio of 71.873 seconds and p95 RTF of 13.511, so both preview performance limits fail. It partially supports `A-017`: CA-validated HTTPS health/static routing passed on `192.168.1.84`; session retries now follow the browser's validated hostname/IP while retaining one fixed participant identity; physical Safari trust, microphone, WebRTC audio, and interruption remain unverified.

The predecessor separately proves one process-local in-memory voice session, conditioned Silero, echo suppression, real local inference, and strict regression gates. Evidence composition does not substitute for executing the entire WebRTC model loop in one run.

Each completed milestone must add a bounded Evidence Record with its source revision, synthetic method, result, artifacts where necessary, `proves`, and `does_not_prove` limits.
