---
type: Work Evidence
title: Matched MLX quantization quality screen
description: Same-probe BF16 and int8 comparison reproduces historical int8 audio and narrows four transcript differences without release promotion.
tags: [work, breeze, mlx, quantization, quality]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T11:23:30Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-017
  authority: coordination
  repository_paths: [scripts/compare_breeze_quantization.py, tests/python/test_breeze_quantization_comparison.py, docs/work/W-20260904-breeze-mps-performance]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Matched MLX quantization quality screen

T-017 under L-014 uses the unchanged fork probe and local recognizer. Root changed only the new comparison wrapper/tests and this bundle. No engine, weights, codec, lock, live service, player, assets, identity or mode changes. Quality remains default, Fast disabled. No microphone, playback, browser/computer use, download or external transfer. [E-016](E-016-quality-localization.md) motivates this diagnostic, not an acoustic conclusion.

## Fixed comparison and integrity

The exclusive mlx-quality-ab-v1 directory retains every attempt/stdout/stderr, corpus, manifest,42 full WAVs and final report. Six verbatim text/instruction pairs: bright-guide zero-based5/6/9, grounded-mentor5, warm-companion5/9. Each uses seeds17/29/42:18 timed outputs and three corpus0/seed17 warmups per arm. BF16 runs first, int8 second, then all36 timed clips receive fresh local ASR. This is a selected diagnostic subset, not a new full release/resident/network benchmark.

All42 unique producer IDs, complete/EOS/not-cancelled states, exact case order, codec/arrival/sample totals, full mono24k PCM16 bytes and hashes pass. All18 int8 probe clips match their historical HTTPS counterparts' sample counts and differ only by the expected round-versus-truncate PCM16 conversion: maximum1 LSB away from zero. Python-integer arithmetic rejects overflow and the incompatible minus32768 endpoint. This is conversion compatibility, not raw-float/codebook equivalence. Fresh int8 ASR exactly reproduces the seven historical flags; eleven clean cases stay clean. ASR joins are hashed report plus ordinal, never ambiguous prompt/seed alone.

Before, between and after producer/ASR phases, the wrapper checks source/model/corpus/kernel identities. Original model content is freshly rehashed: aebc74eac29ac4729fdf0f8c4d3870c1d8cf4efb72e4e24e9316accaa386462d, revision799624c0b4a1daa8db6d28bbd9850043c0270734. Fork a294fe402eda72b7330dd30fd977c829e72137db plus held source digest450b21d39d3682675b03631940f07b86d2079e1e11d118a8e78324bd76cd1056. The manifest records53 source hashes and exact installed Metal artifacts. Torch2.9.1, Transformers4.57.3, qwen-tts0.1.1, MLX/Metal0.32.0; existing offline overlay only. Both arms retain compiled BF16 activations, TorchBF16 text/prefill, FP32 codec, CFG4, temperature0.9, top-k50/top-p1, max750. Int8 affine/group64 covers196 backbone and84 depth linear projections; BF16 leaves both unquantized. Exact module inventories/settings are checked against pinned historical8b71c4ef…; no embeddings/norms/custom heads/codec quantization.

Recognizer config and parsed local marker both match historical mlx-community/parakeet-tdt-0.6b-v3 revisioned2b7e8c15f9aaa0b5772e2efb986255eaef7e15. Twelve installed recognizer sources, dependencies and marker bytes are held/rechecked; recognizer weight digest remains explicitly unverified. All36 ASR counts are recomputed from complete transcripts; original and new WAV/report hashes remain unchanged after recognition.

## Results

| Same-probe arm | Timed audio | p95 first PCM | p95 steady RTF | ASR word errors |
|---|---:|---:|---:|---:|
| BF16 backbone/depth |69.76s /1,674,240 samples|0.825642s|1.088451 — misses0.8|3/189|
| Int8 backbone/depth |75.92s /1,822,080 samples|0.396278s|0.688477 — passes subset threshold|7/189|

Warmups add270,720 BF16 and282,240 int8 samples. Each arm completed21 WAVs; three subprocess attempts exited0, no partial model retry or cleanup failure. Producer attempt elapsed107.422s/72.328s includes loading/warmups and is not a matched inference speedup. Different sampled durations/content prevent treating their wall-time ratio as pure implementation gain. P95 uses nearest rank over18 (the maximum). First PCM is not tap-to-playback or physical sound.

BF16 clears four of the selected int8 transcript differences: bright p6/seed17 A→The, bright p10/seed42 answer→answers, grounded p6/seed17 manageable→manager, warm p10/seed29 answer→answers. Three persist in both: bright p7/seed29 The→But and warm p6/seeds29/42 missing initial A. No previously clean case gains a normalized word error in this subset. Quantization changes sampled speech within the same implementation and nominal seeds; this associates four screen differences with the precision recipe, not proof of acoustic defects, instruction adherence or a component-specific cause. Parakeet is still a single recognizer and no matched listening occurred.

Next bounded candidate: independently select backbone/depth precision and compare both hybrid directions on this unchanged schedule. Higher precision may be affordable in one component; existing stage timings are a hypothesis, not a promised hybrid speedup. Retain the four improved and three shared flags, all eleven clean cases and complete reference outputs. No recipe earns promotion without full quality, latency/resident and device gates.

## Reproduction and held artifacts

```sh
UV_CACHE_DIR=/private/tmp/simo-uv-cache TIKTOKEN_CACHE_DIR=.cache/tiktoken uv run --frozen python scripts/compare_breeze_quantization.py --output-dir .artifacts/breeze-performance/mlx-quality-ab-v1 --run
```

Session84048 exited0; directory is exclusive and must not be reused. Total run199.116s. Sources held after independent review: wrapper0b483526c22fd1335b785602ba704c00f35e1209f5dafc601f0861de5722369c; tests2c3cc70173367b1277ef9a521901440eec9e55758f7d0e7fa261b46cfe6f14f0.

| Local artifact under .artifacts/breeze-performance/mlx-quality-ab-v1 | SHA256 |
|---|---|
| comparison.json |af11c5c0435ef8e4127cba034a29cce0817cd0ef909778f508b3e88e9e0676f2|
| manifest.json |42c3fdfcaeb603a38bd653183ffa9757fa97b29b3dc396b6e79da7416c51fb19|
| corpus.json |6ab4a0e82657f0396a8e14f3212da0d23c14d9aae022c059ac1e4f9c0621be06|
| bf16/report.json |e5b986a750c611cf015d6b0bd388365220f3ecee1bea7da468e34615a6990ca8|
| int8/report.json |c6b45c4abadc0f9438d9419bceb573e3800c0892961291fd16951b752bbbfe12|
| asr/report.json |530ce58186297d5c48c39dddb8b6cced2636a3b8efa6cabbb3b9259690ec561f|

Each attempt.json retains argv/PID/timestamps/exit and stdout/stderr hashes. Comparison.completed means execution and validation completed, never quality acceptance; quality_acceptance is false. Conversion flags are individually explicit rather than inferred from exit0.

## Regression and failure boundaries

Independent [R-123](../results/R-123.md) cleared the held runner before execution; [R-124](../results/R-124.md) independently recomputed all actual output/ASR/PCM joins. [R-125](../results/R-125.md) maps the next selective-precision implementation without changing code or acceptance.

Eight CPU fixtures and canonical164 parent tests pass, with full parent-scoped Ruff/format/ty/BasedPyright. Independent review found a real launcher cleanup bug before any model run: a TERM-ignoring descendant survived leader exit. Fixed cleanup targets only its newly owned process group, reaps the leader, independently waits for group disappearance, escalates to KILL after bounded grace and fails closed on uncertainty. New fixtures cover timeout and nominal leader exit. macOS can briefly return EPERM during process exit; it is conservatively treated as still present, never successful cleanup. The first revised fixture runs exposed that race and failed; final runs pass. Reviewer's owned CPU fixture group was cleaned, no services were targeted.

An escalated full-suite run failed the existing doctor's missing-check count10!=9 when hardware visibility differed; the canonical sandbox rerun passes164. A broad Ruff invocation included four pre-existing services/breeze/serve.py findings outside the parent gate/current lease; the documented parent-scoped gate passes. No unrelated source was changed. Prior fork/web/native gates remain historical unchanged-input evidence, not rerun here. All release/physical gates remain open.
