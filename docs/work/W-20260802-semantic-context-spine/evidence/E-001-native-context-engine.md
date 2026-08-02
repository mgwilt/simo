---
type: Evidence Record
title: Native context engine evidence
description: Records strict compilation and executable tests for the immutable Flecs context-engine revision.
tags: [evidence, native, flecs, tests]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:53:21Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:53:21Z }
simo:
  profile_version: 1
  stable_id: W-20260802-semantic-context-spine-E-001
  authority: evidence
  repository_paths: [CMakeLists.txt, include/simo, src, tests/native]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-semantic-context-spine }
---
# E-001: Native context engine

- Revision: `37ff732690081dff4ef3c02487d9adb6cf9287b2`
- Dirty paths: none.
- Environment: Apple Clang 21; fresh `/private/tmp/simo-verify.2IWfcw`; pinned Flecs `fd9e5f67a933b78e82694c0c5c32a761f9d6d36d`.
- Method: compiled vendored Flecs as C17; compiled all first-party C++20 sources and tests with `-Wall -Wextra -Wpedantic -Werror`; linked a fresh shared library and native test executable; ran the executable.
- Result: pass.

Proves: the immutable native sources compile in this environment; the executable tests demonstrate both queue policies, bounded retention, ordered/revisioned snapshots, earlier-snapshot immutability, counters, Flecs structural observation, JSON escaping, and the C ABI cases they exercise.

Does not prove: other compilers/platforms, CMake generation, realtime latency, lock-free behavior, arbitrary concurrent schedules, memory safety beyond tested paths, persistence, deployment, or semantic quality.
