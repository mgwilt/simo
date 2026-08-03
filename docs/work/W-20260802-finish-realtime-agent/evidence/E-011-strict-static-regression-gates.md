---
type: Evidence Record
title: Strict static regression gates evidence
description: Records the strict Ruff, ty, BasedPyright, hook, build, test, and documentation regression gates established for Simo.
tags: [evidence, quality, typing, lint, hooks, tests, native]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T02:53:48Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T02:53:48Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-E-011
  authority: evidence
  repository_paths: [pyproject.toml, uv.lock, lefthook.yml, .basedpyright-baseline.json, python/simo, tests/python, scripts, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# E-011: Strict static regression gates

- Base revision: `4672689f130020b7805f669dd3fc01dbd94bcd43`.
- Pre-existing dirty paths at start: `python/simo/adapters/pipecat/local_audio.py`, `python/simo/operations.py`, `python/simo/runtime.py`, and `tests/python/test_operations.py`; their functional edits were preserved.
- Environment: macOS Apple Silicon, Python 3.13.7, frozen Ruff 0.14.14, `ty` 0.0.14, BasedPyright 1.39.9, and Lefthook 2.1.10.
- Static method: ran `lefthook run pre-commit --all-files`, which executed whitespace, Ruff format/lint, `ty`, BasedPyright, documentation, and knowledge checks. Ruff selected `ALL` with explicit Simo-policy exclusions; `ty` treated warnings as errors; BasedPyright ran strict across runtime, tests, and scripts with `reportAny`, `reportExplicitAny`, and `reportUnnecessaryTypeIgnoreComment` at error severity. Invoking the installed `.git/hooks/pre-commit` launcher with no staged files confirmed that it reaches Lefthook and truthfully skips jobs whose staged-file set is empty.
- Baseline result: `.basedpyright-baseline.json` records 470 pre-existing strict diagnostics with relative paths. A second BasedPyright run reported zero new errors, warnings, or notes.
- Completion method: invoked the installed `.git/hooks/pre-push` launcher, which rebuilt the native core, ran the Python suite, validated documentation, and ran the knowledge regression suite.
- Result: all pre-commit and pre-push job bodies passed; Ruff reported all 49 first-party files formatted and no lint findings; `ty` passed; BasedPyright reported no new diagnostics; 61 Python tests passed; the native library built; 34 concepts had zero documentation errors and one existing context-size warning; five knowledge tests passed.
- Hook state: `.git/hooks/pre-commit` and `.git/hooks/pre-push` are executable Lefthook launchers and were invoked directly. The managed environment denied Lefthook permission to replace those existing files during automatic synchronization; this did not prevent either launcher from executing the repository configuration.

Proves: the frozen quality tools and their repository configuration are executable; all declared job bodies pass on the recorded working tree; new strict BasedPyright diagnostics fail beyond the explicit baseline; Ruff and `ty` remain baseline-free gates; pre-push covers native and Python execution checks.

Does not prove: that the current working tree is committed or published, that another checkout has installed Git hook files, that the 470 baseline diagnostics are resolved, human microphone or conversation behavior, deployment, or behavior on another platform.
