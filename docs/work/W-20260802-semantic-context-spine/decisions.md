---
type: Work Decision Log
title: Semantic context spine decisions
description: Records bounded implementation choices pending promotion into durable architecture.
tags: [work, decisions, architecture]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:35:00Z }
simo:
  profile_version: 1
  stable_id: W-20260802-semantic-context-spine-DECISIONS
  authority: coordination
  repository_paths: [include, src, python, docs/architecture, docs/interfaces]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-semantic-context-spine }
---
# Decisions

## D-001: Flecs world has one mutation owner

Only `ContextEngine::tick` touches Flecs. Pipecat and other producers enqueue value events through a bounded bridge. This avoids cross-thread ECS mutation and makes sequencing explicit.

## D-002: Systems perform recurring work; observers record structural events

Flecs systems derive recurring context candidates. A Flecs observer is restricted to lightweight structural accounting. The Pipecat observer only filters, deduplicates, and enqueues.

## D-003: Snapshots cross the inference boundary

Consumers receive revisioned immutable snapshot values, not entity handles, live queries, or mutable world access.

## D-004: Overload behavior is explicit

The bounded ingress queue supports `drop_oldest` and `drop_newest`. Counters make information loss observable; neither policy is presented as universally correct.

## D-005: Gepard begins as a local HTTP service adapter

The adapter targets the open-source reference server's `POST /synthesize` WAV response. It does not claim token-streaming synthesis or realtime performance; the upstream CUDA/vLLM runtime remains an external deployment concern.
