---
type: Evidence Record
title: Private relationship learning and recall evidence
description: Records executable safe learning, correction, provenance, isolation, deletion, portability, Flecs projection, and restart recall evidence.
tags: [evidence, memory, learning, provenance, privacy, flecs, recall]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T05:10:22Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T05:10:22Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-E-004
  authority: evidence
  repository_paths: [README.md, python/simo/memory.py, python/simo/persistence.py, python/simo/conversation.py, python/simo/cli.py, python/simo/context.py, python/simo/adapters/pipecat/semantic_turn.py, include/simo/context_engine.hpp, src/context_engine.cpp, tests/python/test_memory.py, tests/python/test_conversation.py, tests/python/test_cli.py, tests/native/context_engine_test.cpp]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# E-004: Private relationship learning and recall

- Source revisions: `ed892816e74e992beddd8c73379c561fad1e8356` and `60ff5d03a94f04e0cf3e6f7951037998da370945`.
- Environment: macOS Apple Silicon, Python 3.13.7, SQLite schema 2, filesystem advisory locks, Flecs 4.1.5, Pipecat 1.7.1.dev14, and the frozen Simo environment.
- Learning method: submitted directly attributed final turns matching narrow allow-listed name, preference, interest, goal, and commitment patterns; materialized active claims with subject, source conversation and event, actor, confidence, freshness, sensitivity, lifecycle, contradiction, and supersession metadata; rejected credential, permission, policy, unmatched, and over-bound inputs without adding them to alias knowledge.
- Isolation and serialization: two aliases in one conversation learned different perspective-bound claims without reading each other's bundle. Two independent store instances concurrently wrote different claims for one alias; the database and materialized OKF bundle retained both under one per-alias cross-process writer lock.
- Correction and privacy: a later direct correction superseded the prior claim while retaining history; operator correction created a linked version; explicit forgetting physically removed the selected database row and materialized content; deleting the source conversation cascaded through derived claim lineage and regenerated affected bundles. Raw audio remained disabled and persona/profile authority pointers did not change.
- Portability and CLI: alias export/import retained claims, lifecycle, and portable provenance without importing conversation rows or another alias's storage. Structured memory list, show, correct, and confirmed forget commands passed deterministic JSON tests. A schema-one fixture migrated to schema two.
- Runtime recall: active claims relevant to room participants became typed Flecs memory entities with participant relations, serialized as bounded values without entity handles, and entered the Pipecat semantic prompt. After twenty synthetic turns and process-owned store/world restart, the deterministic inference fixture answered the recall question with the corrected green-door fact rather than the superseded blue-door fact.
- Result: repository pre-commit passed Ruff `ALL`, format, `ty`, BasedPyright strict, documentation, and knowledge checks. Pre-push rebuilt and tested the native core and passed 80 Python tests, documentation validation, and five knowledge tests.

Proves: `A-004`, `A-006`, `A-007`; restart continuity selects the active corrected claim; private claims remain perspective-bound; provenance and history survive restart and export; prohibited learning does not mutate persona, profile, or private OKF memory; current-participant memory crosses the Flecs-to-Pipecat boundary as immutable values.

Does not prove: open-ended information extraction, language-model recall quality, sensitive-data detection beyond the conservative deny patterns, cryptographic isolation, multi-host locking, live audio, LiveKit transport, human conversational naturalness, latency targets, or autonomous improvement.
