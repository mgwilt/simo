---
type: Work Acceptance
title: Semantic context spine acceptance
description: Defines measurable evidence required for the first executable Simo milestone.
tags: [work, acceptance, tests]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:35:00Z }
simo:
  profile_version: 1
  stable_id: W-20260802-semantic-context-spine-ACCEPTANCE
  authority: coordination
  repository_paths: [include, src, python, tests, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-semantic-context-spine }
---
# Acceptance

- **A-001:** The first-party C++ context engine compiles against pinned Flecs with strict warnings enabled.
- **A-002:** Executable tests prove bounded enqueue behavior for both drop policies and expose accepted, dropped, and processed counts.
- **A-003:** Executable tests prove snapshots are revisioned, immutable values ordered by engine sequence, and bounded by configured retention.
- **A-004:** Python tests prove the native wrapper's contract and Pipecat observation filter/deduplication without requiring a live pipeline.
- **A-005:** Python tests prove the Gepard adapter sends the documented request, validates mono 16-bit WAV output, chunks PCM deterministically, and returns bounded errors without a live model.
- **A-006:** Architecture and interface concepts describe implemented ownership and explicitly leave latency, audio quality, GPU execution, and deployment unproven.
- **A-007:** Documentation validation, knowledge regression tests, runtime tests, and changed-file whitespace checks pass.
