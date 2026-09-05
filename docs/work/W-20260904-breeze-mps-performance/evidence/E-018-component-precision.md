---
type: Work Evidence
title: Independent backbone and depth precision matrix
description: Isolated component weight selectors and a fresh four-arm matrix test the speed and transcript effects without changing live recipes.
tags: [work, breeze, mlx, quantization, quality]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T12:15:45Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-018
  authority: coordination
  repository_paths: [vendor/breeze-tts/breeze_infer/mlx_speech.py, vendor/breeze-tts/breeze_infer/probe_mlx_speech.py, vendor/breeze-tts/tests/test_mlx_speech.py, scripts/compare_breeze_quantization.py, tests/python/test_breeze_quantization_comparison.py, docs/work/W-20260904-breeze-mps-performance]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Independent backbone and depth precision matrix

T-018 under L-016, root sole writer/GPU owner. [E-017](E-017-matched-quantization.md) found four additional int8 transcript flags and three shared flags; full BF16 missed throughput. [R-125](../results/R-125.md) maps the bounded follow-up. Original T-017 evidence is preserved, not pooled as new-source controls. No new weights, kernels, codec/lock changes, training, serving recipe, player/assets, identities, STT/LLM changes, service restart, microphone/playback/computer use, downloads, transfer, trust, paid compute, commits or pushes.

## Implementation and fixed comparison

The speech constructor resolves separate backbone/depth None or integer8 selectors before any model access. An unset sentinel preserves the legacy quant_bits setting; explicit None disables only that component. The isolated probe adds --backbone-quant-bits/--depth-quant-bits choices none/8; omitted flags preserve legacy argv/behavior. Components construct fresh compiled runners, never mutate weights or share graphs/KV caches across arms. BF16 activations/KV, embeddings/custom heads, Torch text/prefill/first-head logits and FP32 codec are unchanged. Actual effective_settings still records full per-component inventories rather than labels alone.

The wrapper retains its default two-arm experiment; --matrix adds both hybrids. Immutable descriptors bind exact labels/component bits/argv, settings, attempt records, validated reports and ASR rows. Exact expected inventories are0/0,196/84,0/84,196/0 backbone/depth eligible linear projections, with affine8-bit/group64 for selected components. Same18 full text/instruction/seed cases and three warmups per arm as E-017; fresh controls run under the new source before hybrids. One seen-ID set spans all84 expected WAVs, including warmups;72 timed ASR rows must match report hash, fixed arm/path and ordinal. Missing/duplicate/swapped arms and mismatched inventories are rejected. The named both-int8 arm alone is compared to historical API PCM. Failure stops later arms and ASR while retaining prior controls and partial output.

Source base remains Simo2ffe040/fork a294fe4 plus held dirty changes. New fork source digest1922a8a0368ceac9824081b4d9cc282969760d9a6ab7e5ff60299df302239b3a;44 other fork source files remain unchanged. Live services continue their previously loaded code/recipes, not this new isolated source identity. Model content freshly rehashes to aebc74eac29ac4729fdf0f8c4d3870c1d8cf4efb72e4e24e9316accaa386462d and corpus remains6ab4a0e82657f0396a8e14f3212da0d23c14d9aae022c059ac1e4f9c0621be06. Existing Torch2.9.1/Transformers4.57.3/qwen-tts0.1.1 and isolated MLX/Metal0.32.0 overlay only. All source/model/corpus/kernel/recognizer identity and full-PCM checks from E-017 remain; recognizer weight digest is explicitly unverified.

Held source SHA256:

| Path | SHA256 |
|---|---|
| fork breeze_infer/mlx_speech.py |8652091dbde72657ce668fa48ea5debcd5eb2b54adf0b2eab65b0ce42de54efe|
| fork breeze_infer/probe_mlx_speech.py |f57c28384051d0ca276309ada6988de6a3ad086b5104d2215fb7ef961f56d4ca|
| fork tests/test_mlx_speech.py |cf1b64d90d82b4f4b81b69e635808efbd96e88afff9df01ee1e523312485e40a|
| scripts/compare_breeze_quantization.py |2bc09a52af10b80d79a182fa448dae4f6df4433e3e55bd4a68d224daf937f061|
| tests/python/test_breeze_quantization_comparison.py |9ef4c54c2a537218d85962ed3dd7c940c69bfca5a32b0a6a9f7b6a518c4ba01c|

## Verification and actual execution

Root69 focused/200 full overlay tests pass; locked reference83 pass/three optional MLX skips. Canonical Simo167 tests including11 comparison fixtures, full parent Ruff/format/ty/BasedPyright, focused fork syntax/format and five knowledge tests pass. New tests include explicit None/legacy override forwarding,21 early invalid-value cases, fresh runner objects, full84-ID/72-ASR fixtures, exact settings and third-arm failure preserving controls. Initial lint and test-only possibly-unbound typing failures were corrected before model execution. [R-126](../results/R-126.md) independently clears held component semantics without GPU calls; the matrix guard review independently passes11 CPU fixtures. A wording-only final wrapper change clarifies that original weight contents/live recipes stay unchanged while isolated selector source changes; behavior is unchanged.

Actual matrix session56829 completed/exit0, retaining all outputs in exclusive .artifacts/breeze-performance/mlx-precision-matrix-v1. All five serialized producer/ASR attempts exited0 without generation or cleanup failure; total373.406s includes loading/conversion/warmups/recognition and is not an inference speedup ratio.84 unique completed/EOS/noncancelled full WAVs and72 timed ASR rows pass strict settings/arrival/sample/clock/identity validation. Both fresh controls reproduce all42 prior T-017 timed/warmup WAV bytes and PCM exactly. All18 fresh int8/API comparisons retain the expected1-LSB round/truncate compatibility (864,425 changed sample values), not float/codebook equivalence. Independent R-127 verifies the complete matrix.

## Results and next gate

| Backbone / depth weights | Timed audio | p95 first PCM | p95 steady RTF | ASR errors |
|---|---:|---:|---:|---:|
| BF16 / BF16 |69.76s|0.431029s|1.087687 — fails0.8|3/189|
| Int8 / Int8 |75.92s|0.390399s|0.688251 — passes subset|7/189|
| BF16 / Int8 |72.56s|0.400297s|0.769620 — passes subset|6/189|
| Int8 / BF16 |72.48s|0.422393s|1.007727 — fails0.8|5/189|

Each arm has18 timed outputs plus three warmups. Timed PCM samples respectively1,674,240/1,822,080/1,741,440/1,739,520; warmups270,720/282,240/264,960/264,960. Different sampled durations and content prevent treating wall-time ratios as pure implementation speedup. P95 is nearest rank over18, the maximum; first PCM is not tap-to-playback or audible onset. This is a diagnostic subset, not a resident/network/full release rerun.

Three flags persist across all four arms: ordinal4 bright-guide p7/seed29 The→But, ordinals13/14 warm-companion p6/seeds29/42 omitted initial A. The faster hybrid clears int8's grounded p6/seed17 manageable→manager and warm p10/seed29 answer→answers, but introduces bright p10/seed17 answer→answers (ordinal6); its flags are0/4/6/8/13/14. The reverse clears int8's bright p10/seed42, grounded p6/seed17 and warm p10/seed29 flags, but introduces warm p10/seed42 answer→answers (ordinal17); flags0/4/13/14/17. Across all arms the union is nine flagged cases. Newly flagged cases are retained, not hidden behind improved aggregate counts.

Neither hybrid establishes a clean quality improvement or earns promotion. All quantized arms keep bright p6/seed17 A→The; only full BF16 clears it, but full BF16 misses throughput. Recognition variation associates with component recipes and amplified sampled choices, not proven audible defects or a single component-specific cause. Full unmodified PCM and one local recognizer still cannot adjudicate acoustic completeness or instruction adherence.

Next T-019: implement the CLI-prepared/user-operated matched listening and device evidence interface proposed by R-118 and mapped by T-128. Retain all original/shared/newly flagged cases and clean controls, use complete immutable clips and blinded labels, and distinguish recorded listening from fresh uncached device trials. Further recipe tuning solely against these ASR counts risks optimizing the recognizer screen instead of speech. Actual user observations and physical-onset evidence remain missing; no microphone, autoplay or computer-use permission is inferred. Quality remains default, Fast disabled and all physical/release gates open.

Artifacts under .artifacts/breeze-performance/mlx-precision-matrix-v1:

| Artifact | SHA256 |
|---|---|
| comparison.json |c3deab334d425ba14e9b694c07a9ec18990126fcce7dce42f02775cb75bc95a5|
| manifest.json |dc4b278ef4cf7a783bcf1e171558568d8a81a12dcad062f5fb9e5221680f66e9|
| bf16/report.json |c4322d5bbd11fd86ab672f670a8bdac211c3a8606a8813e997f3d374b2782ec7|
| int8/report.json |a4a64def24cfce1c377df09dccf9f9cb7a095c6798393afdd50ec6b8651f3732|
| bf16-backbone-int8-depth/report.json |35d7a4e7e3fca72199dc7c0abf9ceaf7aed0e9a6f9693d95d018fdae2fabfbd9|
| int8-backbone-bf16-depth/report.json |e58e8240d5b809bedf3903b0bcae07ef1bfc21571c24ece3650e02e75250c401|
| asr/report.json |05acc3cfdae92b717b88b656cdec00d4a718fc7a43480a7e9bd76feaf7a09d75|

The102 expected files include per-attempt argv/labels/timestamps/stdout/stderr hashes, all84 WAVs and the complete reports. Comparison.completed means execution/validation completed; quality_acceptance remains false. No test/benchmark/recognition process remains running after session56829; live services are a separate retained boundary.

Final independent [R-126](../results/R-126.md)/[R-127](../results/R-127.md) and future [R-128](../results/R-128.md) preserve these limits. Both original inference services freshly return ready/nonbusy with unchanged7d52e5a4…/f0cac89f… fingerprints, and both existing LAN pages8443/8444 return200 with the existing CA/hostname verified. No service or assets restarted. The new isolated fork source1922a8a0… is not silently assigned to those already-loaded runtimes.

Final docs139/zero errors/two existing warnings, five knowledge tests and parent/fork diff checks pass. An optional standalone token-count diagnostic selected an uncached encoding and failed DNS; the normal repository validator with its existing cache passes, with no download or runtime change. Parent/fork source holds remain as listed above. No commits/pushes.

Command:

```sh
UV_CACHE_DIR=/private/tmp/simo-uv-cache TIKTOKEN_CACHE_DIR=.cache/tiktoken uv run --frozen python scripts/compare_breeze_quantization.py --output-dir .artifacts/breeze-performance/mlx-precision-matrix-v1 --run --matrix
```
