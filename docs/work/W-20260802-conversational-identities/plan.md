---
type: Work Plan
title: Implement durable conversational identities and the improvement lab
description: Tracks persisted aliases, reviewable multi-turn conversations, private relationship learning, LiveKit pairing, and bounded autonomous runtime improvement.
tags: [work, aliases, conversation, persistence, livekit, learning, evaluation]
status: draft
generated: { by: process:simo-conversation-integration, at: 2026-09-05T17:34:00Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities
  authority: coordination
  repository_paths: [.gitmodules, README.md, include/simo, src, python/simo, services/breeze, web, tests, scripts, docs, pyproject.toml, uv.lock, lefthook.yml, vendor/pipecat, vendor/breeze-tts]
  owner: codex/gpt-5.6-sol
  work:
    schema_version: 1
    id: W-20260802-conversational-identities
    state: active
    mode: read_only
    priority: p1
    accountable: codex/gpt-5.6-sol
    created_at: 2026-08-03T04:11:20Z
    updated_at: 2026-09-05T17:34:00Z
    depends_on: [W-20260802-finish-realtime-agent]
    knowledge_refs: [architecture/semantic-context-spine, architecture/local-macos-voice-pipeline, operations/runtime-observability, governance/DOC-0001-documentation-and-work-management]
    write_paths: []
    next_action: Operator tests the running Fast LAN UI with live conversation and voice instructions; retain open physical-playback and cross-turn speaker-identity limits.
    blocker: null
---
# Implement durable conversational identities and the improvement lab

This plan evolves Simo from one in-memory voice session into a local-first runtime for durable, versioned aliases that can converse, remember, be reviewed, and participate independently in reproducible WebRTC experiments. Runtime behavior and proof remain authoritative over this coordination bundle.

On 2026-09-04 this plan released its broad mutation lease to the dedicated [Breeze performance project](../W-20260904-breeze-mps-performance/). Identity and physical-browser conversation acceptance remain here, available for read-only evidence gathering; new code mutations require a serialized handoff. Completed Breeze integration and E-007 remain historical evidence, not performance-project ownership.

2026-09-05 L-022 (released17:34Z): `process:simo-conversation-integration` was the sole T-011 integration writer from base `2ffe040c322139174ffd8269625c8a34dcd66ccd` plus preserved dirty work. The bounded lease covered live_controls, lan_site, livekit_runtime, config, LiveKit adapters, focused tests, the main web form/assets and this bundle/LAN operations. E-008 records completion and verified reload; R-101/R-102 record read-only reviews. The performance project remains read-only after L-021. No engine, dependency, immutable profile, policy, publication, microphone, or browser-control changes were included. New mutations require a fresh serialized lease.
