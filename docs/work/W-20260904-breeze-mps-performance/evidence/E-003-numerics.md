---
type: Evidence Record
title: Production decoder and codec numerical checks
description: Production decoder and codec numerical checks with bounded evidence and explicit release limits.
tags: [work, breeze, performance, mps]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-04T23:50:49Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-003
  authority: evidence
  repository_paths: [vendor/breeze-tts, services/breeze, python/simo, web, tests]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Production decoder and codec numerical checks

Claim: bounded cached depth correctness and incremental codec consistency can be tested independently of sampled utterance duration.

Source: fork a38d7d1 plus this plan's depth/static/portable changes; pinned production model. Read-only reviewer used three natural prompt/voice prefills on MPS BF16. Exact pairs: “Hello, I am ready to help.” / “Speak calmly and clearly.”; “Wait! The train is leaving now.” / “Speak urgently with excitement.”; “The rain sounds peaceful tonight.” / “Speak softly and slowly.”.

Reference prefixes teacher-force all15 heads into dynamic, static eager and compiled variants. Initial raw-vocabulary comparisons: dynamic/static branch top1 90/90, CFG4 45/45; compiled87/90 and43/45. These are raw logit comparisons, not masked generation-choice proof. Maximum branch/CFG absolute differences dynamic/static0.25/1.375 and compiled0.1875/0.875; all finite, but not universally allclose at atol0.125/rtol0.01. Compilation is not numerically equivalent.

Codec: identical1/3/12 code frames decoded offline and in stateful chunk1 requests; sample counts1920/5760/23040 match, maximum absolute PCM error1.33e-6, SNR114.8–124.5dB, repeated12-frame decode bit-exact with no remaining active request. Acceptance tolerance atol1e-4/rtol1e-3 passed.

Reproduction now lives in `breeze_infer/probe_correctness.py`:
`PYTHONPATH=vendor/breeze-tts services/breeze/.venv/bin/python -m breeze_infer.probe_correctness --model-path .models/Breeze-TTS-2 --compiled`.
The checked-in probe reports valid-codebook-only top1 comparisons, not the initial raw-vocabulary metric. Full JSON is retained in .artifacts/breeze-performance/production-correctness.json when run.
The root rerun also obtained dynamic/static90/90 branch and45/45 CFG valid-codebook top1 agreement; compiled87/90 and43/45. Codec parity/reset results matched. The initial retained file includes a dependency warning preamble; extract its JSON line with `jq -R 'fromjson?'`. The probe now redirects noisy imports to stderr.

Synchronized diagnostic warm stage observations (not production RTF): encoder/projection pair63–65ms once/request; backbone prefill pair49–50ms once; backbone frame pair74–75ms; depth15 heads dynamic220–238ms, static eager115–117ms, compiled41–42ms; codec including host transfer14ms per80ms audio frame. Depth sampling/CFG and backbone output head were excluded. Static/compiled timing also differs in diagnostic warning synchronization. No isolated compilation speedup claim follows.

Proves: bounded numerical checks and bottleneck direction. Does not prove: general numerical equivalence, instruction quality, complete speech, listening acceptance, realtime throughput or CUDA. Verifier: read-only runtime reviewer; root integrates reproducible probe and regression tests.
