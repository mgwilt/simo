---
type: Evidence Record
title: Persisted multi-turn conversation evidence
description: Records executable event ordering, attributed transcript stages, restart resume, export, deletion, and deterministic CLI evidence.
tags: [evidence, conversation, transcript, persistence, resume, cli]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T04:38:18Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T04:38:18Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-E-002
  authority: evidence
  repository_paths: [README.md, python/simo/persistence.py, python/simo/conversation.py, python/simo/cli.py, python/simo/adapters/pipecat/deterministic.py, tests/python/test_persistence.py, tests/python/test_conversation.py, tests/python/test_cli.py, tests/python/test_semantic_pipeline.py]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# E-002: Persisted multi-turn conversations

- Source revision: `59a0c4eac0d72fe22512bc925cc10e47efe067f2`.
- Environment: macOS Apple Silicon, Python 3.13.7, SQLite through the standard library, pinned Pipecat and Flecs dependencies, and the frozen Simo environment.
- Method: created a persisted conversation, ran twenty deterministic synthetic user turns through the Pipecat/Flecs semantic pipeline, recorded final user text and generated, synthesis-submitted, and actually-spoken assistant stages, closed the process-owned store, reopened it, reconstructed context, resumed another turn, completed the conversation, and exported its full event stream and primary review transcript.
- Fidelity check: the primary transcript includes only final user text and actually-spoken assistant text. Generated-but-not-spoken output remains available as a diagnostic event. Events retain participant identity, transport participant identity, monotonic sequence, wall and monotonic timing, interruption state, and active persona/profile versions.
- Result: repository pre-commit passed Ruff `ALL`, format, `ty`, BasedPyright strict, documentation, and knowledge checks. Pre-push rebuilt and tested the native core and passed 74 Python tests, documentation validation, and five knowledge tests.

Proves: `A-002`, `A-003`; twenty turns persist in order; a new store and runtime instance can resume the conversation without losing recorded context; transcript review and JSON export preserve attribution and speech-stage semantics; conversation deletion remains alias-scoped and explicit.

Does not prove: semantic recall of an early fact or later correction by a language model, live microphone or audio-device behavior, real STT/TTS models, raw-audio retention, learned-memory deletion, concurrent conversation isolation, participant-scoped Flecs entities, WebRTC transport, human conversational quality, latency targets, or autonomous improvement.
