---
type: Work Scope
title: Finished Simo product scope
description: Bounds the runnable realtime-agent product, external effects, and deferred production concerns.
tags: [work, scope, product, realtime]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T00:08:12Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-SCOPE
  authority: coordination
  repository_paths: [README.md, include/simo, src, python/simo, tests, scripts, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# Scope

## Finished product

- A documented command starts a Simo voice-agent process from a clean checkout after declared setup.
- Pipecat owns audio/frame flow, interruption, service lifecycle, and the inference pipeline.
- Flecs owns bounded live semantic state and produces immutable context snapshots that are actually injected before text inference.
- Final transcript observations update the world without blocking the media path or duplicating a frame across processor edges.
- Repository OKF concepts can be loaded into a typed Flecs knowledge graph with explicit ID, source, freshness, and runtime-authority boundaries.
- Speech output uses an open-source TTS runtime that runs locally on the target macOS hardware; Gepard remains an optional/reference adapter unless current evidence demonstrates an appropriate Mac-native path.
- STT and text inference are open-source and locally runnable on the target macOS hardware, selected from current primary evidence and hidden behind replaceable interfaces.
- A deterministic headless demo and tests prove the full control/data path without microphones, speakers, model weights, or external services.
- A live demo proves real audio input, transcription, response generation, speech output, interruption, and visible metrics on suitable hardware.
- Configuration, health checks, bounded queues, error reporting, shutdown, and developer documentation are sufficient for another developer to run the demonstrated modes.

## Excluded from the first finished release

- Hosted proprietary inference as a required dependency.
- Multi-tenant production hosting, billing, autoscaling, user accounts, or internet-facing deployment.
- Training or fine-tuning models.
- Treating model output, OKF trust metadata, or prompt content as authorization.
- Claiming non-macOS support or latency performance without executing on that platform/environment.

## Authorization

Repository-local source, tests, documentation, dependency locking, local dependency installation, recoverable generated fixtures, and regular conventional commits are authorized. Preserve `vendor/` pins unless a separate bounded dependency-update decision is recorded. Do not push, deploy, use credentials, download large model weights, clone voices, or synthesize a real person's voice without explicit user authorization. Small model/configuration metadata may be inspected; model weights require a separate explicit download checkpoint.
