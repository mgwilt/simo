---
type: Work Plan
title: Implement durable conversational identities and the improvement lab
description: Tracks persisted aliases, reviewable multi-turn conversations, private relationship learning, LiveKit pairing, and bounded autonomous runtime improvement.
tags: [work, aliases, conversation, persistence, livekit, learning, evaluation]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T04:11:20Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities
  authority: coordination
  repository_paths: [README.md, include/simo, src, python/simo, tests, scripts, docs, pyproject.toml, uv.lock, lefthook.yml]
  owner: codex/gpt-5.6-sol
  work:
    schema_version: 1
    id: W-20260802-conversational-identities
    state: active
    mode: mutation
    priority: p1
    accountable: codex/gpt-5.6-sol
    created_at: 2026-08-03T04:11:20Z
    updated_at: 2026-08-03T04:11:20Z
    depends_on: [W-20260802-finish-realtime-agent]
    knowledge_refs: [architecture/semantic-context-spine, architecture/local-macos-voice-pipeline, operations/runtime-observability, governance/DOC-0001-documentation-and-work-management]
    write_paths: [README.md, include/simo, src, python/simo, tests, scripts, docs, pyproject.toml, uv.lock, lefthook.yml]
    next_action: Implement the versioned local alias and conversation store plus structured alias and conversation CLI commands.
    blocker: null
---
# Implement durable conversational identities and the improvement lab

This plan evolves Simo from one in-memory voice session into a local-first runtime for durable, versioned aliases that can converse, remember, be reviewed, and participate independently in reproducible WebRTC experiments. Runtime behavior and proof remain authoritative over this coordination bundle.
