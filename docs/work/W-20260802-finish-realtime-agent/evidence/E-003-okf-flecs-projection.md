---
type: Evidence Record
title: OKF Flecs projection evidence
description: Records validated two-pass projection, typed runtime relations, provenance fields, and incremental graph refresh.
tags: [evidence, okf, flecs, knowledge, graph]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:40:51Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:40:51Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-E-003
  authority: evidence
  repository_paths: [include/simo, src/context_engine.cpp, python/simo/knowledge.py, tests/native, tests/python/test_knowledge.py]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# E-003: OKF Flecs projection

- Revision: `0a2b2902effbec6db5367107190791b33364e449`.
- Environment: the `E-001` Mac/Python/native toolchain and the repository OKF bundle at this revision.
- Method: rebuilt and ran the strict native suite; ran 24 Python tests, documentation validation, five knowledge tests, and whitespace checks; loaded the real repository bundle through its producer-profile validator; projected it into the same native Flecs world used for semantic context; executed two valid fixture refreshes and one invalid refresh attempt.
- Result: all checks pass. The headless command validates and projects 24 non-reserved concepts and three internal `references` relations. Components preserve OKF path ID, Simo stable ID, type, title, status, authority, source path, verified timestamp, stale date, and content hash. A second fixture refresh updates one concept and removes one stale entity/relation while the earlier snapshot remains unchanged. An invalid bundle leaves graph revision zero.

The C++ projection uses anonymous numeric Flecs entities and typed `ReferencesKnowledge` pairs. Numeric IDs never cross the C++/C/Python boundary. Snapshot data reports documentation identities and provenance only; no field grants authorization or asserts that linked code executed.

Proves: `A-005`; validation precedes mutation; stable documentation IDs are component data rather than Flecs IDs; typed graph relations exist; incremental updates/removal and immutable snapshots execute.

Does not prove: semantic retrieval quality, persistence across process restart, concurrent graph writers, authorization, deployed state, arbitrary OKF extensions, or links other than the implemented internal `references` relation.
