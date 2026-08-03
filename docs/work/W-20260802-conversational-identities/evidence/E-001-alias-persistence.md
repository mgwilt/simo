---
type: Evidence Record
title: Durable alias persistence evidence
description: Records executable alias identity, versioning, portable OKF, SQLite, import/export, CLI, and lifecycle evidence.
tags: [evidence, aliases, persistence, sqlite, okf, cli]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T04:27:30Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T04:27:30Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-E-001
  authority: evidence
  repository_paths: [README.md, python/simo/persistence.py, python/simo/cli.py, python/simo/__init__.py, tests/python/test_persistence.py, tests/python/test_cli.py, pyproject.toml, uv.lock]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# E-001: Durable alias persistence

- Source revision: `c6682778c678271ac26c0859a6674b8562f7be49`.
- Environment: macOS Apple Silicon, Python 3.13.7, SQLite through the standard library, PlatformDirs 4.11.0, and the frozen Simo environment.
- Method: exercised explicit/environment/platform data-root resolution; created aliases; reopened the store through independent CLI invocations; revised persona and runtime-profile versions; inspected the manifest and OKF root; exported and imported an alias into another store; rejected duplicate and path-traversal imports; created, filtered, inspected, and explicitly deleted conversation identity.
- Lifecycle check: targeted persistence/CLI tests ran with `ResourceWarning` promoted to an error after adding explicit rollback/close ownership for every connection.
- Result: repository pre-commit passed Ruff `ALL`, format, `ty`, BasedPyright strict, documentation, and knowledge checks. Pre-push rebuilt the native core and passed 71 Python tests, documentation validation, and five knowledge tests.

Proves: `A-001`; versioned alias identity and private OKF roots persist locally; active persona/profile pointers survive new processes; alias exports are bounded and portable; import fails closed on conflicts and unsafe members; the foundational CLI does not require native/model preflight.

Does not prove: persisted transcript events, assistant speech-stage fidelity, resume context, deletion of learned claims, concurrent multi-process writes under forced failure, relationship learning, Flecs session isolation, WebRTC, latency, conversation quality, or autonomous promotion.
