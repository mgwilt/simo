---
type: Work Plan
title: Finish the Simo realtime agent
description: Tracks delivery of a runnable macOS-first open-source voice agent with Pipecat media, Flecs context, OKF knowledge, and proportional live evidence.
tags: [work, product, realtime, voice, flecs, pipecat, okf]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:20:54Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent
  authority: coordination
  repository_paths: [README.md, CMakeLists.txt, include/simo, src, python/simo, tests, scripts, docs, pyproject.toml, uv.lock, lefthook.yml]
  owner: codex/gpt-5.6-sol
  work:
    schema_version: 1
    id: W-20260802-finish-realtime-agent
    state: active
    mode: mutation
    priority: p1
    accountable: codex/gpt-5.6-sol
    created_at: 2026-08-03T00:02:13Z
    updated_at: 2026-08-03T00:20:54Z
    depends_on: [W-20260802-semantic-context-spine]
    knowledge_refs: [architecture/semantic-context-spine, interfaces/gepard-tts, governance/DOC-0001-documentation-and-work-management]
    write_paths: [README.md, CMakeLists.txt, include/simo, src, python/simo, tests, scripts, docs, pyproject.toml, uv.lock, lefthook.yml]
    next_action: Implement the Pipecat context-snapshot injection processor and a deterministic full pipeline with fake inference providers.
    blocker: null
---
# Finish the Simo realtime agent

This plan coordinates product completion. It cannot declare Simo finished until the headless acceptance loop and the user-visible live voice path have proportional runtime evidence.
