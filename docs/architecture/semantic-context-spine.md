---
type: Architecture Concept
title: Semantic context spine
description: Defines Simo's implemented bounded event ingress, Flecs-owned semantic world, and immutable context snapshot boundary.
tags: [architecture, flecs, pipecat, context, concurrency]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:53:21Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:53:21Z }
sources:
  - id: engine-interface
    resource: ../../include/simo/context_engine.hpp
    title: Simo context engine C++ interface
  - id: engine-implementation
    resource: ../../src/context_engine.cpp
    title: Simo Flecs context engine implementation
  - id: observation-implementation
    resource: ../../python/simo/adapters/pipecat/observer.py
    title: Simo Pipecat observer adapter
  - id: context-tests
    resource: ../../tests/native/context_engine_test.cpp
    title: Simo native context engine tests
simo:
  profile_version: 1
  stable_id: DOC-0002
  authority: architecture
  repository_paths: [include/simo, src, python/simo, tests/native, tests/python]
  owner: unassigned
---
# Semantic context spine

## Implemented boundary

Simo has one native `ContextEngine` owner for the live Flecs world. Producers do not receive the world, entity handles, queries, or mutable components; they enqueue transcript values through the C++ or C ABI, and consumers receive a reference-counted immutable `ContextSnapshot` value.[^engine-interface]

```text
Pipecat frame pushes
        |
        v
filter + bounded dedupe
        |
        v
bounded native event queue -- explicit drop policy + counters
        |
        v
ContextEngine::tick (only Flecs mutation owner)
        |
        +--> transcript entities ChildOf simo.Conversation
        +--> recurring scoring system
        +--> structural accounting observer
        |
        v
revisioned immutable ContextSnapshot
```

The queue assigns a local monotonic sequence at ingress, supports `drop_oldest` and `drop_newest`, and reports accepted, dropped, processed, queued, retained, and structural-observation counts. `tick` drains and sorts pending events, performs world mutation, runs Flecs systems, applies bounded retention, and constructs a sequence-sorted snapshot.[^engine-implementation]

## Flecs ownership

- `simo.Conversation` is the root runtime entity for the current engine instance.
- Each retained transcript is a Flecs entity related to the conversation with `ChildOf` and carries private `TranscriptSegment` state.
- `simo.ScoreContext` is a recurring Flecs system that derives private `ContextCandidate` salience.
- `simo.ObserveTranscriptStructure` is an `OnSet` observer used only for lightweight structural accounting.
- Components and entity IDs stay implementation-private. The stable cross-language identity is the event sequence inside a snapshot, not a Flecs handle.[^engine-implementation]

This is intentionally not an OKF runtime graph. OKF concept paths, Markdown links, `simo.stable_id`, Work Plan state, and Flecs entity/relation IDs remain separate namespaces.

## Pipecat observation boundary

`PipecatSemanticObserver` watches frame pushes, ignores interim and non-transcription frames, deduplicates the same final frame as it traverses multiple processors, and performs one bounded native enqueue. It never calls `tick`, queries Flecs, performs inference, waits on external I/O, or injects context back into the pipeline.[^observation-implementation]

The framework-neutral `FinalTranscriptObservationBridge` owns the bounded dedupe cache, so filtering behavior can be tested without a live transport. Queue overload remains the native engine's responsibility and is visible through its counters.

## Snapshot contract

A snapshot contains a revision plus ordered context items with sequence, speaker, text, finality, and derived salience. Existing shared snapshots do not change when later ticks advance the world. Native tests demonstrate queue policies, retention, ordering, revision changes, JSON escaping, C ABI access, structural observation, and preservation of earlier snapshot values.[^context-tests]

The current score is deliberately mechanical: final transcripts receive a base weight and bounded text length adds a small increment. It is scaffolding for extensible systems, not a claim about semantic relevance or model quality.

## Concurrency and lifecycle

- Enqueue and statistics access are thread-safe bounded operations.
- `ContextEngine::tick` is the sole Flecs mutation path and must be driven by one owner thread.
- Snapshots are safe value boundaries for downstream inference; no consumer may retain live world access.
- The current engine is in-memory only. Restart persistence, replay, distributed ownership, multi-conversation routing, and deletion policy are not implemented.

## Evidence boundary

Verified revision `37ff732690081dff4ef3c02487d9adb6cf9287b2` compiles with Apple Clang under strict first-party warnings and passes native and Python boundary tests. This proves the local dataflow and API behavior exercised by those tests. It does not prove realtime latency, lock-free behavior, deterministic behavior across different thread schedules, production capacity, security, persistence, deployment, or context usefulness.

[^engine-interface]: `include/simo/context_engine.hpp` and `include/simo/context_engine_c.h` at revision `37ff732690081dff4ef3c02487d9adb6cf9287b2`.
[^engine-implementation]: `src/context_engine.cpp` at revision `37ff732690081dff4ef3c02487d9adb6cf9287b2`.
[^observation-implementation]: `python/simo/observation.py` and `python/simo/adapters/pipecat/observer.py` at revision `37ff732690081dff4ef3c02487d9adb6cf9287b2`.
[^context-tests]: `tests/native/context_engine_test.cpp`, `tests/python/test_context.py`, `tests/python/test_observation.py`, and `tests/python/test_pipecat_adapters.py` at revision `37ff732690081dff4ef3c02487d9adb6cf9287b2`.
