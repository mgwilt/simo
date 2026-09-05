---
type: Evidence Record
title: Fresh HTTPS corpus and resident-model measurements
description: Ten matched HTTPS cohorts pass bounded throughput and simulated playback checks while seven ASR candidates and physical quality gates remain open.
tags: [work, breeze, performance, residency, quality]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T09:50:00Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-015
  authority: evidence
  repository_paths: [python/simo, scripts, web, services/breeze, vendor/breeze-tts]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Fresh HTTPS corpus and resident-model measurements

T-015/A-001/A-006/A-007 under L-011, root sole writer/verifier; read-only independent [R-116](../results/R-116.md)/[R-117](../results/R-117.md). Claim: fresh unpaced HTTPS throughput and retained-trace playback meet their numerical screens with the same candidate before/with idle Simo weights. This does not satisfy physical playback or quality release. Seven non-segmentation ASR flags remain unresolved.

## Method and identity

[E-014](E-014-https-benchmark-contract.md) records held code/test hashes, admission, dependencies and canonical manifest3f74496a70b633e9b29b7a4615808662acc49bd61a0b1ccc381a0fa89645868a. Candidate/source/model/lock unchanged from [E-012](E-012-experimental-serving.md): runtime f0cac89f955ee07d3f1b1bfac9d2cd8f5a2e1be5dcdb8ae4be828c66cdb24acd, executable d4ba5fd3…, Torch BF16 prefill, compiled MLX BF16/int8 group64 backbone/depth, FP32 codec, CFG4/temperature0.9/top-k50/top-p1/max750 frames and explicit seeds17/29/42. No CFG, instruction text, model, dependency, player policy or source changed between cohorts.

For each condition, default short10×3 seeds, default long2×3, then separate full10×3 cohorts for warm-companion, bright-guide and grounded-mentor. Every cohort has three untimed warmups repeating its own index0/seed17/instruction; no pooling variants or filtering successful rows. Total252 timed outputs plus30 warmups,282 globally unique actual request IDs, all BYPASS and matched completed/EOS/noncancelled producer metrics. Timed PCM totals29,341,440 samples/1222.56 seconds. Retained WAVs include every timed output; warmups retain hashes/metrics, not separate WAVs.

All tests ran serially against the same already-warm service over certificate-verified `https://192.168.1.83:8444` from this Mac, not another Wi-Fi device. Each request includes fresh TLS setup; arrivals are captured before copying and EOF wall excludes metrics polling. Unpaced RTF is not credit-paced browser throughput. Cold startup was not repeated; historical startup measurements remain historical.

```sh
SIMO_BREEZE_ENDPOINT=http://127.0.0.1:7861/v1/audio/speech \
UV_CACHE_DIR=/private/tmp/simo-uv-cache TIKTOKEN_CACHE_DIR=.cache/tiktoken \
uv run --frozen simo breeze benchmark --url https://192.168.1.83:8444 \
  --ca-file '/Users/mike/Library/Application Support/mkcert/rootCA.pem' \
  --warmups 3 --limit 10 --seeds 17,29,42 --suite SUITE \
  --instruction-id INSTRUCTION --audio-dir NEW_DIRECTORY --json
node web/scripts/replay-preview.mjs COMPLETED_REPORTS
uv run --frozen python scripts/evaluate_breeze_audio.py CONTROL_REPORTS
```

The first resident-long launch failed with sandbox `Operation not permitted`, exit2, before a manifest/evidence directory or measured request; its empty stdout is preserved as `mlx-https-v1-resident-long.json`. An explicitly permitted fresh attempt is `resident-long-r2`, not a dropped timed sample. Every actual measured cohort completed on its single attempt. No browser, microphone, external audio transfer, trust installation, publication or Quality restart.

## Numerical results

All values are per-cohort p95; render is **simulated**, not physical sound.

| Condition / cohort | Timed | First PCM s | Steady RTF | Total RTF | Simulated first render s |
|---|---:|---:|---:|---:|---:|
| Control / default short |30|0.406785|0.692129|0.799839|0.794667|
| Control / default long |6|0.428236|0.685239|0.697875|0.816000|
| Control / warm-companion |30|0.355758|0.690804|0.803185|0.741333|
| Control / bright-guide |30|0.364230|0.695336|0.843068|0.752000|
| Control / grounded-mentor |30|0.316851|0.692977|0.803762|0.704000|
| Resident / default short |30|0.312300|0.691982|0.799711|0.704000|
| Resident / default long |6|0.331662|0.687025|0.699174|0.725333|
| Resident / warm-companion |30|0.318407|0.690909|0.816260|0.709333|
| Resident / bright-guide |30|0.320890|0.698114|0.831144|0.714667|
| Resident / grounded-mentor |30|0.314676|0.692273|0.798041|0.704000|

All126 timed control/resident pairs and15 warmup pairs have identical PCM hashes/frame counts/prompt/seed/instruction. Replay uses the actual held player/worklet with15360-frame/640ms reserve,48000-frame credits/ring cap and120-second total cap. All252 clips preserve every PCM sample, complete and have zero **modeled** queue underruns. The independent reviewer reproduced the replay byte-for-byte. Ports/context/output timestamps/render clock remain simulated; no physical onset, remote jitter or live consumer backpressure claim.

Holder PID7936/session40862 used the existing Simo loaders and explicitly evaluated parameters. Ready at1788600343639838000 Unixns; every control ended before its startup1788600340581198000. Before/after status timestamps bracket each complete resident cohort, including warmups, with constant3,663,420,368 active MLX bytes and3,621,223,180 evaluated parameter bytes. It stopped at1788601395291830000 and exited0. Models: Parakeet ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15 and Qwen3.5-4B-4bit0e7ffd5c629ef7719d4cbc04069232580bfa9d9c; markers/sources/dependencies are in the hashed holder report. This is idle weight residency, not concurrent inference or OS page pinning; full resident weight contents were not rehashed.

## Cancellation and quality screens

Four actual TLS disconnect trials target fixed long/0,seed17/default: two before response headers, two after3840 PCM bytes/one codec frame. Before-header trials observed no response application bytes; matching producer metrics additionally recorded zero PCM/codec frames. All new request IDs end cancelled/not completed. After-PCM concurrent requests return409. Observed cancellation-to-idle47.02–93.85ms; each immediate **same-case** retry completes exactly matching the647040-sample/26.96-second control PCM471115c64135624b9213b43a4182b68266a97ff7dd216d6b52a2f401934c05f8. Eight unique trial/retry IDs, equal lifecycle/control/retry manifests, all four attempts retained. All12 preview-cache paths/hashes/mtimes unchanged. Review corrected an initially unrun script's short-vs-long retry, response-header validation and failure-path cache snapshot before execution; the corrected script is b2dbf7d387c3f0dc67eff0799266e2a2786f0091751c85d970f5cdf813649c96. This is HTTP disconnect, not a physical browser Stop test.

Fresh local Parakeet ASR screened all126 control WAVs after holder/lifecycle exit. The126 resident WAVs are byte-identical, so no duplicate ASR was needed. Default short0/294 word errors. Long raw6/396 consists of tradeoffs versus trade offs/trade-offs segmentation; raw flags retained. Warm-companion3/294, bright-guide3/294, grounded-mentor1/294 are **seven unresolved** possible text defects:

- warm-companion: index5 seeds29/42 omit initial article A; index9 seed29 answer→answers.
- bright-guide: index5 seed17 A→The; index6 seed29 The→But; index9 seed42 answer→answers.
- grounded-mentor: index5 seed17 manageable→manager.

Indices are zero-based. These may be generation or recognizer errors; neither is adjudicated by this screen. Full matched reference/candidate listening and instruction adherence remain unaccepted. E-011 PCM differed from these new default files by at most1 PCM16 LSB, explained by probe rounding versus API truncation, so its ASR was not silently reused. Next bounded work should localize all seven flags against matched reference/MLX candidates before promotion, then add the [R-118](../results/R-118.md) user-operated acceptance runner. Do not cherry-pick seeds or alter text/instructions to hide defects.

## Artifacts and release state

All paths below are under `.artifacts/breeze-performance/`. The audit contains exact filenames/SHA256s for every control/resident cohort and holder brackets; reports contain full source/build/runtime/settings and request-level rows.

| Artifact | SHA256 |
|---|---|
| mlx-https-v1-full-audit.json | a171c67256c999bdffb9390c4dcb96d7a762c1659944491583ded18638190b0e |
| mlx-https-v1-full-replay.json | 3353f3b18fc61575aec193f69f49bafc63a1bd6f6e8325bb1bc6c2e680bce1dd |
| mlx-https-v1-resident-holder.jsonl | 76b77f7deaddf0e0c6744061c79a0ce76e5c98c1aae03f7f0413ffdf6d99cfa1 |
| mlx-https-v1-lifecycle.json | 81358a0a0f476a843546cd758fc9fe45d6ad9afd56e033dbbf6f6f9592643df9 |
| mlx-https-v1-control-asr.json | 30016a1e4a7d1d08c2e4145614329c9185fe830a961b979e22138f707793ae34 |
| mlx-https-v1-served.json | 19689727e2f833400fa5a612939993f8cbd2d34f2f965f6bb92c3b9b3ec2ed44 |

Final verified TLS asset checks: all five original Quality files equal unchanged web/dist; all seven experimental files equal the held separate build. Both services ready/nonbusy at original fingerprints. Experimental HTTPS PID90526/session5485 replaced PID56024/session69335, which exited130; inference PID98272/session98210 and Quality PID46660/session62395 remain unchanged. No holder or benchmark remains running.

147 Simo Python/36 web/5 knowledge tests, TypeScript, full parent Ruff/format/ty/BasedPyright and diff checks pass. A final knowledge-test invocation initially omitted the existing tokenizer cache and failed DNS; rerun with TIKTOKEN_CACHE_DIR=.cache/tiktoken passed all five, without a download. E-012 fork/native and E-013 build gates are retained unchanged, not rerun for unchanged sources/assets. Documentation structure does not establish runtime acceptance.

Proves bounded throughput/replay/residency/lifecycle at the recorded source and settings. Does not prove cold startup, remote-device LAN timing, actual acoustic onset, observed device interruptions, concurrent STT/LLM load, numerical model equivalence, voice/instruction acceptance or CUDA support. A-001/A-006/A-007 remain open and Fast stays disabled; Quality remains default. Goal active; no commit or push.
