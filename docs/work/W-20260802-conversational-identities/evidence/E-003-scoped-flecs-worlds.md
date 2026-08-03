---
type: Evidence Record
title: Scoped Flecs conversation world evidence
description: Records executable native and Pipecat proof for isolated alias and conversation worlds with bounded participant-attributed snapshots.
tags: [evidence, flecs, context, isolation, participants, pipecat]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T04:47:58Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T04:47:58Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-E-003
  authority: evidence
  repository_paths: [include/simo/context_engine.hpp, include/simo/context_engine_c.h, src/context_engine.cpp, src/context_engine_c.cpp, python/simo/context.py, python/simo/conversation.py, python/simo/adapters/pipecat/semantic_turn.py, tests/native/context_engine_test.cpp, tests/python/test_context.py, tests/python/test_semantic_pipeline.py]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# E-003: Scoped Flecs conversation worlds

- Source revision: `f43d1105374b454a9eaf7359cab7e2834bb3438d`.
- Environment: macOS Apple Silicon, Clang C++20, Flecs 4.1.5 pinned as vendored source, Python 3.13.7, Pipecat 1.7.1.dev14, and the frozen Simo environment.
- Native method: created two independent `ContextEngine` worlds with different alias, conversation, local participant, remote participant, and transport identities; represented conversations and participants as Flecs entities; interleaved different transcript updates; and inspected immutable serialized snapshots from each world.
- Pipecat method: created a scoped native world, passed final attributed transcript frames through the observer and semantic-turn processor, and asserted that every inference snapshot retained the stable alias, conversation, local participant, complete participant set, and transport identities.
- Boundary check: scoped engines reject unknown transcript speakers before native mutation. Snapshot JSON contains value records only and exposes no Flecs entity ID, handle, database connection, or mutable storage object.
- Result: repository pre-commit passed Ruff `ALL`, format, `ty`, BasedPyright strict, documentation, and knowledge checks. Pre-push rebuilt and tested the native core and passed 75 Python tests, documentation validation, and five knowledge tests.

Proves: `A-005`; every persisted runtime invocation creates a native world scoped to one alias and conversation; two active worlds do not exchange transcript state; native graph identity reaches Pipecat inference only through a bounded immutable value snapshot; transport participant identity remains attributable.

Does not prove: semantic recall quality, alias OKF relationship projection, concurrent multi-process storage isolation, LiveKit subscription policy, WebRTC audio, participant joins or leaves during an active room, latency targets, or autonomous improvement.
