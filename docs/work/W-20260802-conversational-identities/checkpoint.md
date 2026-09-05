---
type: Work Checkpoint
title: Conversational identities checkpoint
description: Captures the current resumable state for durable aliases, Breeze-TTS-2, and trusted-LAN browser acceptance.
tags: [work, checkpoint, aliases, breeze, livekit, lan]
status: draft
generated: { by: process:simo-conversation-integration, at: 2026-09-05T17:34:00Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-CHECKPOINT
  authority: coordination
  repository_paths: [docs/work/W-20260802-conversational-identities]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# Checkpoint

Current T-011 checkpoint,2026-09-05: root `process:simo-conversation-integration` completed bounded live session controls and response grouping under L-022. Base `2ffe040c322139174ffd8269625c8a34dcd66ccd` plus prior dirty performance work; no commit/push, no engine/dependency/profile mutations. E-008 and R-101/R-102 record tests, review corrections, proof gaps and launch. The live UI resumes the existing conversation on `https://192.168.1.83:8443` using the unchanged Fast sidecar on7861. Session revision1 selects a non-brief prompt and1024-token budget; original generic voice instruction/CFG4/seed42 remain editable/unchanged respectively. Server restart restores saved defaults; no physical audio/browser or release acceptance is claimed.

Next action: operator refreshes the LAN page and tests conversation/voice instructions using Apply now. Stable speaker conditioning remains a separate open limitation, not a promise that grouping fixed perceived identity. The performance project stays read-only after L-021; this plan released L-022 after final runtime verification and is read-only. Later overlapping mutations require serialized ownership. Broader identity and physical-media gates remain open. Use the verified IP URL: the historical configured hostname failed local name resolution during the final check.

## Historical integration checkpoint

The following2026-09-02 baseline is preserved as history, including its earlier addresses, measured timings and physical Safari acceptance boundary. E-007 is not rewritten. The current user requests CLI/script verification and no Safari automation.

- Base revision: `f5a039f5fa23877dc2aa39b234280b00c8909c6c`.
- Integration state: Simo implementation commit `c037f5f`; owned Breeze fork commit `a38d7d1`; the fork pin and ownership documentation are included in this follow-up.
- Completed predecessor: `W-20260802-finish-realtime-agent` at `b6b3386`.
- Completed `T-001` at `c668277`: platform-default or overridden local data root, schema-versioned SQLite ownership, stable aliases, immutable persona/runtime-profile versions, private portable OKF bundles, safe bounded export/import, conversation identity, structured CLI, and explicit deletion.
- Completed `T-002` at `59a0c4e`: ordered attributed events, distinct generated/submitted/spoken assistant stages, transcript review/export/delete, and process-restart resumption.
- Completed `T-003` at `f43d110`: one isolated Flecs world per alias/conversation, typed participant graph identity, bounded immutable context snapshots, and fail-closed unknown speakers.
- Completed `T-004` at `ed89281` and `60ff5d0`: serialized private relationship learning, provenance and freshness, correction and forgetting, portable alias OKF materialization, Flecs memory projection, and restart recall.
- Historical `T-005` transport layer at `00033bd` and `5cc44b9`: room-scoped tokens, allow-listed audio-only subscriptions, remote SID preservation through Pipecat, a structured `simo lab prove-webrtc` command, and an observed two-process bidirectional WebRTC PCM exchange through self-hosted LiveKit 1.13.5 with zero self-echo or identity errors.
- Completed `T-005` at `a69c11e` through `6499101`: local STT/LLM/TTS providers, Silero and turn handling, bounded session-event persistence, RoomIO, isolated context snapshots, and a persisted alias runtime are owned directly by LiveKit Agents.
- Replacement `T-006` room proof at `6499101`: two independent OS processes and distinct LiveKit SIDs completed the real local-model audio loop with two spoken turns each, three remote synthetic-audio transcriptions, reviewable attributed transcripts, zero self-echo, unexpected identities, attribution errors, duplicate turns, or incomplete generated turns, and no raw audio retention. One spoken turn was interrupted; latency, barge-in rates, and held-out scenario floors remain open.
- Interactive headset slice at `fac700e`: `simo talk --alias …` starts one persisted LiveKit alias and one native PlatformAudio human participant. Live doctor passed on the declared M3 Ultra with default Arctis Nova Pro recording/playout; a bounded observed startup produced distinct participant SIDs and clean persistence/shutdown without raw audio. Human conversation quality remains operator evidence, not an automated acceptance claim.
- Active `T-010` implementation: Breeze is the default TTS backend; owned MPS fork `a38d7d1…`, upstream base `0072588…`, and model `799624c…` are pinned; the fork provides eager PyTorch MPS while the loopback launcher owns Simo health policy; runtime-profile v2 captures voice design, instruction, CFG scale, and seed while v1 profiles resolve to Qwen rollback.
- Fork-native proof: the owned fork passed 31 tests, loaded the real model on MPS, reported bfloat16 and 24 kHz, and returned an uncached 23,040-byte PCM response with the declared headers.
- Observed Breeze result on the M3 Ultra: model health reported MPS, bfloat16, and 24 kHz; 3 warmups plus 10 samples produced non-empty PCM with p50/p95 first audio 51.243/71.873 seconds and p50/p95 RTF 13.163/13.511. The declared preview gate failed on both limits, and Breeze remains selected by operator decision.
- Observed LAN host result: Caddy served `https://mikesMacStudio.local:8443` and `https://192.168.1.84:8443`; CA-validated health and static requests passed. Operator testing exposed two defects: a failed connection exhausted the one-use token, and the IP fallback still returned the mDNS signaling URL. Both are corrected with retryable fixed-identity tokens and validated request-host signaling. A mic-free curated voice palette is implemented with local WAV caching. Physical Safari microphone/audio proof remains pending.
- Verification: native build; 115 Python tests; Ruff; Ruff format; `ty`; BasedPyright strict; TypeScript; production web build; documentation validation; five knowledge regression tests; and diff whitespace passed. All three curated previews were then rendered through the live HTTPS endpoint and reported cached.
- Architecture decision: `D-009` makes LiveKit Agents the sole realtime orchestrator and makes the Pipecat proof a predecessor baseline. No Pipecat path will be deleted until LiveKit Agents replacement tests and a live room run pass.
- Current milestone: `T-010` completes physical trusted-LAN Safari acceptance before work returns to `T-006` Pipecat removal.
- Blocker: installing and trusting the local CA on an iPhone or iPad and operating its microphone requires the user on that physical device.
- Next action: install the generated mkcert root CA on the test device, enable certificate trust, open the LAN URL, grant microphone access, and record the physical media result.
