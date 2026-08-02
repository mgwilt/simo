---
type: Evidence Record
title: Pipecat and Gepard adapter evidence
description: Records pinned Pipecat observer and Gepard TTS adapter behavior without requiring model weights or a live server.
tags: [evidence, pipecat, gepard, python, tests]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:53:21Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:53:21Z }
simo:
  profile_version: 1
  stable_id: W-20260802-semantic-context-spine-E-002
  authority: evidence
  repository_paths: [python/simo, tests/python, pyproject.toml, uv.lock]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-semantic-context-spine }
---
# E-002: Pipecat and Gepard adapters

- Revision: `37ff732690081dff4ef3c02487d9adb6cf9287b2`.
- Dirty paths: none.
- Environment: locked optional runtime with Pipecat `1.7.1.dev14` from submodule commit `b114a367a32166207712e8a9c352215a6e24a0db`; Python safe-path execution from `/private/tmp`; native library freshly built for `E-001`.
- Method: ran 11 Python unit tests with `SIMO_CORE_LIBRARY` pointing to the fresh immutable build.
- Result: pass. Pipecat emitted a non-fatal NLTK `punkt_tab` download warning because outbound access was intentionally unavailable.

Proves: Python/native snapshot interoperability; observer final-frame filtering and deduplication; bounded dedupe eviction; documented Gepard request formation; WAV constraints; deterministic PCM reconstruction; real pinned Pipecat frame types; context ID propagation; and bounded non-200 error frames for the exercised cases.

Does not prove: a live Pipecat pipeline or transport, a live Gepard server, model loading, CUDA/vLLM, audio correctness or quality, interruption, streaming time-to-first-audio, concurrency, deployment, or network failure exhaustiveness.
