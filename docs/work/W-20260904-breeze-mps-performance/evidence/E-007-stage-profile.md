---
type: Evidence Record
title: Current MPS model-stage profile
description: Production-weight controls and synchronized diagnostics prioritize depth decoding while a new compiled plus SDPA candidate still misses Fast throughput.
tags: [work, breeze, mps, profiling]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T04:52:04Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-007
  authority: evidence
  repository_paths: [vendor/breeze-tts/breeze_infer/profile_stages.py, vendor/breeze-tts/tests/test_profile_stages.py]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Current MPS model-stage profile

Claim: depth plus sampling dominates the current SDPA path, and adding compiled static depth improves this small screen but still fails the throughput target. Simo base2ffe040 with prior changes; fork a294fe4 plus only the new profiler/tests. Model799624c, BF16 model/FP32 codec, torch2.9.1/Transformers4.57.3/qwen-tts0.1.1; no weights or dependency locks changed. Serving Quality process stayed unchanged; isolated diagnostics used the same host.

Commands (no browser):

```sh
PYTHONPATH=vendor/breeze-tts services/breeze/.venv/bin/python -m breeze_infer.profile_stages \
  --model-path .models/Breeze-TTS-2 --attention sdpa --depth-cache dynamic --warmups 1 --limit 3
PYTHONPATH=vendor/breeze-tts services/breeze/.venv/bin/python -m breeze_infer.profile_stages \
  --model-path .models/Breeze-TTS-2 --attention sdpa --depth-cache compiled --warmups 1 --limit 3
```

Each probe uses one warmup,3 existing correctness prompts/instructions, seed42/CFG4/temperature0.9/top-k50/top-p1/repetition1. Each prompt has an uninstrumented control and a synchronized whole-stage run. This is not the10-prompt/3-seed release corpus. JSON records effective settings, model marker/config digest, executable source digest, stage samples and EOS/frame counts. Final profiler captures source before loading and hashes delivered Float32 audio; earlier dynamic report used the identical unedited source throughout its run and has frame counts but no audio hashes. It does not rehash the complete model package; no weight mutation occurred during these tests.

| Recipe | Control total RTF range | Profile depth+sampling per frame | Control/profile validation |
|---|---|---|---|
| SDPA/dynamic cached depth |2.508–2.687|133.50–137.25ms|19/24/74 frames match; all EOS |
| SDPA/compiled static depth |1.794–1.844|79.83–81.38ms|28/25/66 frames and Float32 audio hashes match; all EOS |

Compiled controls first PCM0.226/0.229/0.340s; load plus compile7.07s. Output durations differ between implementations, so wall time alone is not a speedup comparison. Normalized RTF and per-frame depth timings improve, but even the best short control remains over2x the0.8 release target. Compilation remains an unpromoted numerical candidate; identical control/profile hashes establish only that instrumentation did not change those compiled outputs, not equality with reference generation or voice acceptance.

Dynamic synchronized aggregate per80ms audio frame: depth+sampling134.50ms, sequential backbone pair38.30ms, codec12.76ms, remaining14.43ms. Counts are N depth/N codec/2 prefills/2N backbone decode calls. These boundaries force synchronization: backbone excludes output head/CFG; codec excludes Float32 CPU/NumPy conversion. The third profiled run was8% faster than its control, exposing run/order variance; stage shares are diagnostic, not a strict additive production bound. Depth is the next priority; paired backbone alone cannot close the gap.

Artifacts under .artifacts/breeze-performance:

- stages-sdpa-dynamic.json SHA25610687bc8b12665192109ec3b5353f4607c9cf03c206d12a8a6fda4bb4d7135e3; source digestbb1216e5ea86a484691afc7779f6bbbbb930123df1ca0a7d73744a4150ed3727.
- stages-sdpa-compiled.json SHA256cc32bc3fcd58c3f7983ca7dbab9c689a1b621226f45938eed70b83a93835214c; source digest8c577c1d75458aecc6071f867dd34cf619717022007e23a2129d34ea13b21dd4.

Early probe failures (duplicate audio_samples report key and optional inputs_embeds during backbone decode) produced no accepted report. Both fixed; four profiler tests cover restoration/failure cleanup and cache-based labels. A strict Simo-parent linter invocation against the separately styled fork reported annotation/style diagnostics; the fork's focused syntax/error check and formatter are used for these two files, without weakening Simo's normal gates.

Proves: actual production-weight MPS block observations, completed short controls, current next-step priority. Does not prove: Fast p95, physical playback, long/resident release, matched listening, reference numerical equivalence, MLX speed, or CUDA behavior. Next: [MLX depth mapping](../tasks/T-106.md) and a bounded production-weight prototype including heads/CFG/sampling, then combine demonstrated wins with remaining runtime work. Verifier: root integration process, with independent read-only dynamic-profile review; freshness2026-09-05.
