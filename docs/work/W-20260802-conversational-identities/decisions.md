---
type: Work Decision Log
title: Conversational identities decisions
description: Records locked storage, identity, learning, LiveKit Agents ownership, privacy, and promotion choices.
tags: [work, decisions, aliases, okf, livekit, evaluation]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T05:37:38Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-DECISIONS
  authority: coordination
  repository_paths: [python/simo, include/simo, src, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# Decisions

## D-001: Use local application data with portable boundaries

The platform data directory owns aliases and a versioned SQLite store. `SIMO_DATA_DIR` overrides the platform default for tests and portable operation. Alias export/import includes its manifest and OKF bundle plus explicitly selected conversation data.

## D-002: Keep episodic and semantic authority separate

SQLite is transactional authority for conversation, event, experiment, and promotion records. An alias's OKF bundle is durable semantic authority for persona and learned claims. Flecs is an isolated live projection of selected values from both.

## D-003: Preserve stable identity while allowing persona evolution

`AliasId` never changes. Persona, voice, model, prompt, and mechanics are immutable versions selected by an atomic active-profile pointer. The optimizer may create and promote new versions but cannot alter platform policy.

## D-004: Store private perspectives, not shared hidden truth

Each alias stores attributed claims from its own perspective. One alias cannot read another's bundle. Contradictions supersede active claims without destroying provenance history.

## D-005: Record actually spoken assistant output

Conversation review distinguishes generated text, TTS-submitted text, and text confirmed spoken before completion or interruption. Only final user transcription and actually spoken assistant output form the primary transcript.

## D-006: Keep content storage separate from operations telemetry

Conversation text belongs to the explicit local conversation store. Existing operational events remain aggregate and content-free. Raw audio is experiment-scoped and off by default.

## D-007: Use self-hosted LiveKit as the first room substrate

Self-hosted LiveKit remains the first and current room substrate. The initial Pipecat-based transport proof preserves remote participant IDs and remains evidence for the underlying room path, but `D-009` supersedes Pipecat as the active orchestration choice.

## D-008: Auto-promote only through immutable evaluated versions

All runtime configuration, including models, voices, prompts, and personas, may evolve. Code, permissions, retention, learning policy, evaluation floors, and budgets cannot. Promotion requires a material held-out win with hard floors and always retains an atomic rollback target.

## D-009: Use LiveKit Agents as the sole realtime orchestrator

LiveKit Server owns WebRTC transport and rooms. LiveKit Agents owns RoomIO, VAD, endpointing, interruption, STT/LLM/TTS scheduling, turn lifecycle, and session events. Simo-owned adapters connect local models, immutable Flecs snapshots, transcript persistence, privacy-safe operations, and evaluation without placing storage or OKF writes on the audio callback path.

Running Pipecat and LiveKit Agents together is rejected because it creates competing frame, cancellation, buffering, participant, observer, and tuning ownership. Using only the low-level LiveKit RTC SDK is also rejected for now because it would require Simo to reimplement the turn and voice-pipeline lifecycle already supplied by LiveKit Agents. Pipecat is removed only after replacement unit and live-room evidence passes so the migration cannot erase the last working path prematurely.

Promotion target: [LiveKit Agents runtime](../../architecture/livekit-agents-runtime.md).
