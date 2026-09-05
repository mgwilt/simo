---
type: Evidence Record
title: Breeze matched candidate screening
description: Breeze matched candidate screening with bounded evidence and explicit release limits.
tags: [work, breeze, performance, mps]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-04T23:50:49Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-002
  authority: evidence
  repository_paths: [vendor/breeze-tts, services/breeze, python/simo, web, tests]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Breeze matched candidate screening

Claim: progressive first PCM improves substantially; no candidate has established realtime sustained generation.

Environment: M3 Ultra 512 GB, macOS 26.5.2, Python 3.13.12, torch/torchaudio 2.9.1, Transformers 4.57.3, qwen-tts 0.1.1. Simo base 2ffe040; fork base a38d7d1 plus the performance changes in this plan. Every JSON records the loaded source digest and effective settings; early screens predate model-content hashing. Same model revision 799624c, instruction, CFG4, temperature0.9/top-k50/top-p1; no lower-CFG speed claim.

| Screen | Warmups / prompts / seeds | p95 first PCM (s) | p95 steady RTF | Artifact under .artifacts/breeze-performance |
|---|---|---|---|---|
| Original locked reference | 3 / 10 / 1 | 49.165 | not separately recorded | baseline-a38d7d1.json |
| Initial cached streaming/eager | 1 / 3 / 1 | 0.809 | 6.972 | streaming-eager-screen.json |
| SDPA plus integer-index head optimization | 1 / 3 / 1 | 0.873 | 3.027 | streaming-sdpa-screen.json |
| Compiled static depth/eager attention | 1 / 3 / 1 | 0.576 | 3.058 | streaming-compiled-screen.json |
| Native int8/eager | 1 / 3 / 1 | 0.648 | 5.640 | streaming-int8-screen.json |
| Native int4/eager | 1 / 3 / 1 | 0.827 | 6.290 | streaming-int4-screen.json |
| Unquantized SDPA finalist screen | 3 / 10 / 3 | 0.665 | 3.390 | sdpa-30-samples.json |
| Final Quality/eager default | 1 / 3 / 1 | 0.620 | 6.340 | final-quality-screen.json |

Method: start each isolated sidecar, then `simo breeze benchmark --warmups N --limit N --json`; seed42. Quantized runs additionally use `--audio-dir` to retain complete listening WAVs. First-request timing is retained separately in newer warmup_samples. These short screens are nearest-rank p95 (the maximum of three), not a release population. Baseline total p95 RTF is 9.954.

Output durations differ despite matched prompts/settings; compare normalized RTF and frame/stage counts, not wall time alone. Early eager and SDPA screens also differ by the later direct output-head view: their difference is not an isolated attention speedup.

The30-sample screen used seeds17/29/42, all completed with EOS. Total p95RTF3.442; model load2.319s, first unused-service request PCM1.548s (not a whole-machine cold-cache measurement). Artifact SHA256:0284e29ad7dec794c6ff433cbc1e8807f1d633fefb6d643eb9bc70055cfa32e7. First-PCM is not tap-to-playback: the0.8 steady-RTF release gate fails by over4x.

Proves: actual MPS incremental PCM, completed matched model corpus, source/settings attribution, failed throughput gate. Does not prove: tap-to-physical-sound, full-corpus quality, zero underruns, full resident-model release suite or CUDA support. First implementation smoke failed at EOS because it compared text PAD instead of codebook PAD; fixed and regression-tested, never counted as success.

Verifier: root integration process; freshness: this checkout and host on 2026-09-04. Historical identities E-007 remains unchanged.
