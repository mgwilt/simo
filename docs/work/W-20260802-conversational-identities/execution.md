---
type: Work Execution
title: Conversational identities execution
description: Orders storage, conversation, learning, LiveKit Agents migration, WebRTC, evaluation, promotion, and documentation milestones.
tags: [work, execution, milestones, aliases, livekit]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-09-02T07:02:46Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-EXECUTION
  authority: coordination
  repository_paths: [python/simo, include/simo, src, tests, scripts, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# Execution

| ID | Milestone | Acceptance | State |
|---|---|---|---|
| T-001 | Implement local alias manifests, profile/persona versions, SQLite schemas, export/import, and foundational CLI | A-001, A-002, A-003 | complete |
| T-002 | Add persisted multi-turn recording, assistant speech-stage capture, transcript review, resume, and deletion | A-002, A-003, A-004, A-007 | complete |
| T-003 | Add conversation/participant-scoped Flecs projections and bounded context retrieval | A-004, A-005 | complete |
| T-004 | Add safe private relationship learning and alias OKF materialization | A-006, A-007 | complete |
| T-005 | Replace Pipecat orchestration with LiveKit Agents provider/node/event adapters; preserve the former path until replacement unit evidence passes | A-005, A-007, A-015 | complete |
| T-006 | Prove and persist the full two-process local-model WebRTC loop, then remove Pipecat and its submodule | A-008, A-013, A-015 | active |
| T-007 | Add held-out scenarios, mechanics and conversation evaluators, and synthetic ground-truth metrics | A-009, A-010, A-012 | pending |
| T-008 | Add candidate search, automatic promotion, canarying, rollback, and persona lineage | A-011, A-012 | pending |
| T-009 | Promote durable architecture/interfaces/operations, run full verification, and close | A-013, A-014, A-015 | pending |
| T-010 | Pin and integrate Breeze-TTS-2, benchmark MPS, serve one alias through trusted LAN HTTPS/WSS, and complete physical Safari acceptance | A-016, A-017 | active |
