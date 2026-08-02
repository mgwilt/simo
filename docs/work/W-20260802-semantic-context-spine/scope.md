---
type: Work Scope
title: Semantic context spine scope
description: Bounds the first executable Simo milestone and its external-effect limits.
tags: [work, scope, runtime]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:35:00Z }
simo:
  profile_version: 1
  stable_id: W-20260802-semantic-context-spine-SCOPE
  authority: coordination
  repository_paths: [CMakeLists.txt, include, src, python, tests, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-semantic-context-spine }
---
# Scope

## Included

- A C++20 Flecs-owned semantic context engine with a bounded ingress queue, deterministic update ordering, bounded transcript retention, and immutable JSON snapshots.
- A stable C ABI and Python wrapper so the realtime Python plane never mutates the Flecs world directly.
- A Pipecat observer that filters final transcription frames, deduplicates repeated frame pushes, and performs only bounded enqueue work.
- A Pipecat Gepard HTTP TTS service targeting the open-source reference server's `/synthesize` WAV contract.
- Unit and integration-style tests that do not require model weights, a GPU, network access, or a live voice transport.
- Proposed architecture and interface concepts promoted only to the level supported by executable evidence.

## Excluded

- STT or text-inference model selection and execution.
- Downloading Gepard weights, installing CUDA, running vLLM, voice cloning, or proving realtime latency/audio quality.
- Deployment, credentials, hosted APIs, external publication, or changes under `vendor/`.
- General-purpose memory retrieval, OKF-to-Flecs synchronization, multi-agent orchestration, or production persistence.

## Authorization boundary

Repository-local implementation, tests, and regular conventional commits are authorized. Pushes, deployments, credential use, model downloads, and vendored dependency mutations are not part of this milestone.
