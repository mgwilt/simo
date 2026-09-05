---
type: Evidence Record
title: Matched MLX residency and real cancellation
description: Identical-seed local producer comparisons with evaluated Simo model weights and real codec lifecycle recovery.
tags: [work, breeze, mlx, performance]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T07:10:07Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-011
  authority: evidence
  repository_paths: [vendor/breeze-tts/breeze_infer/probe_mlx_speech.py, vendor/breeze-tts/tests/test_mlx_speech.py, scripts/hold_breeze_resident_models.py, tests/python/test_breeze_residency.py]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Matched MLX residency and real cancellation

T-012 measures the isolated real-PCM producer before and with Simo's existing STT/LLM weights held in a separate process. It also exercises actual cancellation/failure cleanup and immediate deterministic retries. No serving route, Quality settings, original weights, codec implementation, dependencies or identities changed. Fast remains unaccepted.

## Method

Same M3 Ultra, pinned original Breeze model and BF16-activation/8-bit group64 backbone/depth recipe as [E-010](E-010-mlx-speech.md). CFG4, temperature0.9, top-k50, top-p1, sampling enabled, repetition1.0,750 iterations; existing FP32 codec. Torch2.9.1/Transformers4.57.3/qwen-tts0.1.1 plus isolated MLX/MLX-Metal0.32.0 overlay. Kernel identities and quantization coverage/exclusions remain E-008/E-009. Reference weights were not rehashed this continuation; each report retains model marker, source, dependencies, effective recipe and corpus hashes.

All four cohorts use exactly the same source, instructions, corpus bytes and seeds17/29/42, with three successful warmups per cohort. Short is ten prompts × three seeds; long is two prompts × three seeds. Each request is uncached and timed from preparation through generation/codec/cleanup; steady RTF uses actual first-to-last PCM arrivals divided by subsequent output duration. Unix timestamps enclose requests/reports for resident-lifetime checks; performance intervals use the monotonic clock. Timings are not HTTP, browser scheduling or audible start.

```sh
PYTHONPATH=vendor/breeze-tts UV_CACHE_DIR=/private/tmp/simo-uv-cache \
uv run --offline --project services/breeze --frozen \
  --with mlx==0.32.0 --with pytest==8.4.2 \
  python -m breeze_infer.probe_mlx_speech \
  --model-path .models/Breeze-TTS-2 --quant-bits 8 --warmups 3 \
  --corpus .artifacts/breeze-performance/mlx-short-corpus.json \
  --seeds 17 29 42 --lifecycle-checks --audio-dir NEW_DIRECTORY
```

Use mlx-long-corpus.json and omit lifecycle checks for long cohorts. Capture stdout as a fresh report; WAV evidence directories are exclusive and failed/partial audio is never a preview cache entry. Probe exits unsuccessfully for failed warmups, timed requests or requested lifecycle checks.

Resident holder, in the existing main Simo environment:

```sh
HF_HUB_OFFLINE=1 UV_CACHE_DIR=/private/tmp/simo-uv-cache \
uv run --frozen python scripts/hold_breeze_resident_models.py \
  --report .artifacts/breeze-performance/mlx-matched-resident-models.jsonl
```

Keep stdin open; issue `status` before/after each cohort and `exit` after completion. The holder uses Simo's existing loaders, materializes both parameter trees with mx.eval/synchronize, retains both models, and records live process/memory/source/model identities. Qwen performs one initial token before benchmarking; STT/LLM inference does not run concurrently with measured Breeze. Main environment MLX0.32.0, MLX-LM0.31.3, Parakeet-MLX0.5.2 and Transformers5.12.1 remain separate from Breeze's locked Transformers4.57.3 process.

Parakeet revision ed2b7e8:697 unique arrays/1,254,104,332 parameter bytes. Qwen3.5-4B-4bit revision0e7ffd5:924 arrays/2,367,118,848 bytes. Holder PID64510 reports3,663,453,136 active MLX bytes and86,030,568 cached bytes at ready, before/after both resident cohorts and final stopped event. Status timestamps bracket all resident report/request intervals; the holder started after both controls finished and exited successfully after the long comparison. This proves evaluated idle-weight retention, not OS page-pinning or concurrent inference. Local markers match effective configuration; full weight digests were not reverified.

## Completed results

Nearest-rank p95; six-sample long p95 is its maximum. All four cohorts are terminal and complete.

| Cohort | Completed | First PCM p95 | Steady RTF p95 | Total RTF p95 |
|---|---:|---:|---:|---:|
| Short control |30/30|0.392729s|0.694963|0.799316|
| Short, STT/LLM resident |30/30|0.390373s|0.695910|0.799035|
| Long control |6/6|0.416892s|0.683903|0.695479|
| Long, STT/LLM resident |6/6|0.407247s|0.684971|0.696218|

All36 resident PCM hashes equal their matched controls. All six long-control hashes also equal the earlier E-010 long PCM, so that retained ASR defect screen applies to identical audio. Each long cohort produces171.92s of audio; resident maximum interchunk arrival gap70.31ms is below80ms audio per chunk but does not establish LAN underruns. The paired cohorts show no material throughput degradation in this bounded idle-resident comparison; it is not a concurrency stress benchmark or statistical generalization beyond the fixed suite.

After all benchmarks and holder termination, `scripts/evaluate_breeze_audio.py` screened the30 control-short WAVs locally using pinned Parakeet ed2b7e8:0/294 word errors, no flagged prompt. Hash equality extends this screen to the resident-short audio. Long raw ASR retains6/396 errors, all tradeoffs/trade offs segmentation, with complete alphanumeric-normalized passages as E-010 records. These screens do not establish matched listening, instruction adherence or numerical equivalence; the earlier seed44 trailing-word flag remains historical evidence, not erased by this different-seed cohort.

## Actual interruption and retry

Both short cohorts run four extra trials after timing: close the consumer iterator after first PCM; set its cancellation event; inject a consumer exception after first PCM; inject a codec decode exception on the second frame. The real model, codec pool, worker and inference lock execute. A concurrent second iterator must reject while the first retains ownership. Cleanup must leave no active requests, worker, locked inference or poison; partial output must not be marked complete. The probe then immediately reruns the same prompt/seed and requires EOS/completion and PCM SHA equality with the baseline.

All eight trials pass. Control cleanup4.54–18.56ms; resident-short5.13–18.61ms. The codec-fault clock begins inside the injected failing decode, before worker cleanup, not after consumer observation. Exceptions are restored only after joining the worker. This proves actual runtime cleanup/retry after first PCM and a decode failure, not HTTP disconnect/browser Stop, prefill/backpressured cancellation, codec-open/close failure recovery or audible behavior.

## Source and verification

Simo base2ffe040/fork a294fe4 plus preserved experimental files. Executable digest ee0491c98c8621e5a5e819cf10d0a41eda4bcdba28c5176afb57addff50ff83a; inference unchanged from E-010, probe adds timestamps/lifecycle controls. Root is sole L-007 writer and holds executable files unchanged for independent T-110 review. Holder SHA591f29cc53cf30cf83e800a725519ee48f20bd531e3a0fc998de589ed79cba0b; holder test SHAcc31f4ca63e4d4e71e2cd2bac0ec96493cd388e3c5288400afa5cd80622052a0.

Current checks:153 full fork overlay tests,65 locked tests/three optional skips,127 Simo Python tests,5 knowledge tests; full parent lint/format/ty/basedpyright and focused fork syntax/format pass. Initial invalid plan-mode spelling was corrected; the failed/hung test run was interrupted and then fully rerun successfully. No failed attempt is counted as acceptance. [R-110](../results/R-110.md) independently verifies held source,100 WAV artifacts/request IDs, all matching settings and resident lifetime bounds, and runs three CPU-only holder tests. No blocking finding remains in this bounded milestone. All benchmark/ASR/test/holder processes terminated; original Quality health remains ready/non-busy with unchanged7d52e5a4 fingerprint.

Local .artifacts/breeze-performance report SHA256:

- mlx-int8-matched-control-short.json:343e5f010247eb8310ceca458d6e491e527ee669dff8816e247e734c5a3d38a7.
- mlx-int8-matched-control-long.json:d3d26b3d514b7d2efc0bddf7d0ad1b8a266fb9db06b0aa32b093dd63db35cb9c.
- mlx-int8-matched-resident-short.json:089f27ddb837e189e593979181c15474f6b5c9c77c4f657166c308fdbc029991.
- mlx-int8-matched-resident-long.json:fd889b1c0e75fc9b8f0c1e771f5f929a0be699753f70914a0448d9be1d71a8ae.
- mlx-matched-resident-models.jsonl:9f8b20ba018c2b91ec741cf480e619d0a6c0f6350c4bf3f9b1b36e2938cb3900.
- mlx-int8-matched-short-asr.json:7e7b4f1ff16886a069d537aa54535d15dc2e31bd09bfe0edc8a4d93148f022d0.

Proves bounded matched producer throughput and actual isolated lifecycle recovery. Does not prove Fast release, LAN tap-to-playback, device underruns, matched listening, reference Torch/MLX numerical identity or CUDA. No commits/pushes, training, exports, paid compute, data transfer or computer use. A-006/A-007 and the autonomous goal remain open.
