---
type: Work Execution
title: Finish Simo execution
description: Orders research, core integration, inference, knowledge, operations, and live acceptance milestones.
tags: [work, execution, milestones]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:08:12Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-EXECUTION
  authority: coordination
  repository_paths: [README.md, include/simo, src, python/simo, tests, scripts, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# Execution

| ID | Milestone | Acceptance | State |
|---|---|---|---|
| T-001 | Research and lock current Mac-native TTS, STT, text inference, and target hardware contracts | A-006, A-007 | complete |
| T-002 | Implement typed configuration, preflight, lifecycle, and headless entrypoint | A-001, A-009 | active |
| T-003 | Implement Pipecat context-snapshot injection and deterministic headless loop | A-002, A-003, A-004 | pending |
| T-004 | Implement repository OKF-to-Flecs knowledge graph and refresh | A-005 | pending |
| T-005 | Implement selected open-source STT and text inference adapters | A-006 | pending |
| T-006 | Implement and harden the selected Mac-native TTS cancellation and interruption path | A-007 | pending |
| T-007 | Add observability, privacy defaults, shutdown, and operator documentation | A-009, A-010 | pending |
| T-008 | Prove live three-turn interruptible voice conversation on the declared Mac | A-007, A-008 | pending |
| T-009 | Promote durable knowledge, independently verify, and close | A-010, A-011 | pending |
