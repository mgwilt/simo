---
type: Evidence Record
title: MLX depth performance and numerical limits
description: Isolated production-weight MLX depth experiments demonstrate stage-level gains while numerical and end-to-end Fast gates remain unmet.
tags: [work, breeze, mlx, quantization]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T05:24:03Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-008
  authority: evidence
  repository_paths: [vendor/breeze-tts/breeze_infer/mlx_depth.py, vendor/breeze-tts/breeze_infer/probe_mlx_depth.py, vendor/breeze-tts/tests/test_mlx_depth.py]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# MLX depth performance and numerical limits

Claim: a standalone MLX depth implementation, including all 15 heads, CFG and sampling, reduces measured stage time. None of its recipes establishes reference equivalence, utterance quality or Fast release. Simo base 2ffe040; owned fork a294fe4 plus the new MLX module/probe/tests and prior profiler. Original weights, serving process and locks remain unchanged. Root ran the GPU experiments; mlx_mapping and fast_review independently inspected mapping, tests, artifacts and timing boundaries without GPU work.

## Method

Apple M3 Ultra 512 GiB, macOS 26.5.2. Pinned model revision 799624c; Torch 2.9.1, Transformers 4.57.3, MLX/MLX-Metal 0.32.0. MLX and pytest 8.4.2 use an isolated UV overlay in /private/tmp/simo-uv-cache; MLX-LM and Transformers v5 were not introduced. Core API documentation was fetched through Context7 and checked against installed 0.32 signatures. Model marker is recorded; no complete weight-package rehash was performed in these probes.

```sh
PYTHONPATH=vendor/breeze-tts UV_CACHE_DIR=/private/tmp/simo-uv-cache \
uv run --offline --project services/breeze --frozen \
  --with mlx==0.32.0 --with pytest==8.4.2 \
  python -m breeze_infer.probe_mlx_depth \
  --model-path .models/Breeze-TTS-2 --attention sdpa
```

Repeat with --attention eager, then --attention sdpa --quant-bits 8, then --quant-bits 4. All four main reports use three instruction-conditioned first-frame prefills from E-003, three warmups and ten timed repetitions per prompt. Reference prefills/greedy paths use seed 42. Timed sampling uses seeds 1000–1009; different Torch/MLX generators do not produce matched samples from equal seeds. Effective depth recipe: CFG 4, temperature 0.9, top-k 50, top-p 1.0. This is not the ten-prompt/three-seed release suite.

Teacher forcing compares every head against separate full-prefix eager Torch branches, with F32 CFG, valid-codebook top1, margins, max error, RMSE and relative L2. A separate whole-frame compiled teacher-forcing graph reports the same metrics; full greedy generation is checked independently. Timing covers fresh per-frame KV state, projection, transformer, heads, CFG, reserved-token masking and sampling. MLX results are evaluated and synchronized. Seed/key setup is outside v2 timings; complete input/output bridges are measured separately. The Torch timing control is cached eager, not the best compiled+SDPA path from E-007. Graph compilation and first calls are recorded separately, but later candidates benefit from previously warmed kernels.

## Results

| MLX candidate | Compiled depth p95 across 3 prompts | Branch / CFG top1 agreement | Exact greedy frames |
|---|---|---|---|
| BF16 eager |61.66–62.08 ms|87/90; 41/45|1/3|
| BF16 SDPA |57.57–57.91 ms|89/90; 43/45|2/3|
| 8-bit affine SDPA |32.66–32.99 ms|88/90; 43/45|1/3|
| 4-bit affine SDPA |29.75–30.02 ms|69/90; 31/45|0/3|

Compiled/uncompiled recorded numerical metrics agree within each recipe; they do not equal the Torch reference. Maximum relative CFG L2 errors are 0.0762, 0.0949, 0.0956 and 0.2172 respectively. BF16 SDPA mismatches include an exact top1 tie and a 0.03125 margin; that identifies sensitive cases, not harmless audible impact. Full-frame autoregression can amplify an early token difference. Four-bit saves only about 3 ms over eight-bit while causing substantially more drift; retain it as an unpromoted result, not the next default candidate.

Torch cached-eager control p95 is about 200–218 ms. That comparison establishes a stage-level opportunity only. Eight-bit input readiness bridge is 1.61–1.68 ms, output bridge 0.367–0.377 ms; these are one observation per prompt/candidate, not bridge p95. An earlier BF16 output bridge observed a 14.8 ms first-use outlier. Eight-bit load was 1.73 s and conversion/quantization 0.296 s. No real audio was produced by this microbenchmark. Prior backbone pair about 38 ms plus codec about 13 ms already make depth-only optimization insufficient for the complete 64 ms/frame Fast budget.

Quantization covers exactly 84 attention/MLP linears, four actual matrix shapes and 76.7815% of **depth weight bytes**, not whole-model bytes: 666,894,336 / 868,560,896. Group size 64, affine packed weights with BF16 scales/biases. Selected packed storage is 354,287,616 bytes at eight-bit and 187,564,032 at four-bit. Embeddings, norms, projectors, custom/output heads and codec are excluded. Nothing was exported or overwritten.

## Verification and artifacts

Final fork suite: 90 passed with the MLX overlay; locked reference environment: 65 passed, one optional MLX module skipped. Simo Python: 124 passed. The 25 MLX tests cover precision fixtures, sampling/filter order, reserved tokens, teacher-forced caches, evaluated A→B→A state/key isolation, invalid inputs, all four production quantized shapes at paired prefill/decode, and exact excluded-weight preservation. Focused source lint passes. Independent-review fixes corrected implicit sampling defaults, unevaluated lazy tests, missing value/cache checks and exact quantization name selection.

Initial quantization tests incorrectly conflated batch-size-dependent arithmetic with branch contamination: six bit-exact batch1/batch2 assertions failed. Same-shape tests now replace the other branch and require exact unchanged conditional output; all pass. Quantized arithmetic versus dequantized weights separately requires relative L2 below 0.01. This is kernel evidence, not a relaxed model-quality gate. Precision drift remains explicitly unaccepted.

Artifacts in .artifacts/breeze-performance (SHA256):

- mlx-depth-eager-3.json: 8c984075367fe5a1817d48baa6d05856997bb877da5f90c9a05fb35beec61833.
- mlx-depth-sdpa-3.json: 3fcf12792a427a1797a072526fa27af01fbf9df461b81b5b902aff39c773654b.
- mlx-depth-sdpa-int8-3.json: eb231004d994f777ccd3249417ed91ac4a329bba7415ae36a4b3c0c7852b44f6.
- mlx-depth-sdpa-int4-3.json: 00f2a301f49c4a10bc380f731a13137c03e7347af6f0fe15ac5ee5d86981410f.
- Initial one-prefill mlx-depth-eager-1.json: 19c95b52e4afc4108cd4376329118eeb235316f77b75a51495488e1d6f1b7730. Schema v1 includes seed/key setup inside timing and excludes MLX input evaluation; superseded by v2 for comparisons.

BF16 reports executable digest 44d51fab726703776460c38eac2bac2cab8afea1a75cf47e18257688521c8ad0; quantized reports 4340ccc6b9eb47b37ec70eb20e1e499680a8c7399bfc478d3490fdccf6884ae1. Final name-set hardening and excluded-content tests followed those probes without changing the selected matrices or arithmetic. Quantized reports pin actual MLX kernel artifacts: libmlx.dylib SHA256 1876795e05b3434925e745fbf6e9f0c8c0446b666224c9d881609ab353e94e51; mlx.metallib 1518c08860738b08dc4563ddcf380a08dec4e6ad146c0d54888790e80656e9e3.

Proves: evaluated production-weight depth performance, bounded numerical differences, kernel shape/branch tests and a viable isolated MLX dependency route. Does not prove: numerical equivalence, later frames, complete/intelligible audio, instruction adherence, LAN startup/underruns, resident-model throughput, physical listening or CUDA. Probe exit zero means finite logits, not acceptance. Quality health remains ready/non-busy with original fingerprint 7d52e5a4dfa21507711928e32a26a758ecca1fb93871e8c9afefedd6dc05c96b. Next: localize BF16 operation drift on identical Torch inputs and map/test the actual Qwen3 backbone before any candidate integration. Freshness 2026-09-05.
