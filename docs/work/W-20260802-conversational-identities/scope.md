---
type: Work Scope
title: Conversational identities scope
description: Defines included capabilities and the privacy, authority, evidence, and external-effect boundaries for durable conversational aliases.
tags: [work, scope, privacy, authority, aliases, livekit]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T04:11:20Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-SCOPE
  authority: coordination
  repository_paths: [python/simo, include/simo, src, tests, scripts, docs, pyproject.toml, uv.lock]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# Scope

## Included

- Local application-data storage for stable aliases, persona and runtime-profile versions, private OKF bundles, conversations, memories, experiments, promotions, exports, and deletion.
- Session-scoped Flecs worlds and participant-aware immutable context snapshots for multiple aliases and conversations.
- Structured CLI surfaces for aliases, conversations, memory, local deterministic talking, and experiments.
- Final user and actually spoken assistant transcript capture with generated-but-unspoken diagnostics, timing, interruption, provenance, and configuration versions.
- Safe perspective-bound relationship learning, correction, forgetting, freshness, contradiction history, and OKF materialization.
- Self-hosted LiveKit room support with independent Simo participants and remote-audio-only subscription.
- Synthetic two-alias experiment execution, evaluation profiles with hard floors, automatic promotion, canary verification, and rollback.
- Mac-native open-source models and synthetic or prerecorded acceptance; no human timing or participation is required.

## Excluded and protected

- Raw audio retention is off unless an experiment explicitly enables it.
- Persona, model output, transcript content, or learned knowledge cannot grant tools, permissions, or authorization.
- Automatic improvement cannot modify code, platform permissions, retention rules, learning safety policy, evaluation floors, or experiment budgets.
- Aliases cannot read another alias's private files or database state; knowledge crosses the boundary only through attributed conversation or explicit import.
- Direct transcript injection cannot satisfy the WebRTC end-to-end gate.
- Self-play and model-judge results do not prove subjective human naturalness.
- No cloud deployment, remote publication, hosted LiveKit provisioning, or paid provider is authorized by this plan.
