---
type: Evidence Record
title: MLX numerical localization and backbone continuation
description: Same-input precision diagnostics and production Qwen3 continuation screens justify an isolated full-utterance experiment but not Fast promotion.
tags: [work, breeze, mlx, quantization]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T06:07:44Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-009
  authority: evidence
  repository_paths: [vendor/breeze-tts/breeze_infer/mlx_depth.py, vendor/breeze-tts/breeze_infer/mlx_backbone.py, vendor/breeze-tts/breeze_infer/probe_mlx_operations.py, vendor/breeze-tts/breeze_infer/probe_mlx_backbone.py]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# MLX numerical localization and backbone continuation

T-010 bounded result, not numerical/quality/Fast acceptance. Same M3 Ultra, model799624c, Torch2.9.1/Transformers4.57.3 and isolated MLX/MLX-Metal0.32 overlay as [E-008](E-008-mlx-depth.md). Original weights, environments and Quality serving are unchanged. Root owns implementation; mlx_mapping reviewed architecture/cache boundaries and fast_review reviewed diagnostic/timing claims.

## Same-input arithmetic

Diagnostic hooks compare MLX primitives using the exact Torch-produced inputs, never different autoregressive prefixes. Three selected depth heads from instruction-conditioned prefills produce six branch executions; hooked and unhooked Torch outputs are bit-identical. Hooks restore in finally. This synchronized/copy-heavy experiment is not timing evidence.

Among72 attention-stage cases, RoPE, attention dot, F32 softmax and F32-internal SiLU controls agree exactly. BF16 attention multiplication by a Python scale agrees in only10/72 cases when MLX first rounds the scalar to BF16. Multiplying in F32 and casting the result back agrees72/72; a positive/negative compiled regression test protects this correction. Linear kernels still differ in316/510 cases, though mean element mismatch is0.0171%; maximum relative L2 is0.000520. One of150 RMSNorm cases differs. The scale correction is real, not the sole source of accumulated model drift.

Corrected eager depth rerun: branch top1 89/90, CFG42/45, exact greedy frames0/3, compiled p95 61.82–62.25ms. Local numerical correctness does not monotonically improve full greedy agreement. Full reference equivalence remains unaccepted; the SDPA implementation was not altered by this eager correction.

## Backbone implementation and method

Standalone Qwen3 continuation preserves nested configuration, learned per-head Q/K norms, audio embedding sum precision, separate EOS head, unequal logical positions and per-row masks. Torch performs unchanged text/prefill; already-rotated KV transfers once. Explicit immutable MLX state uses128-slot chunks with bounded expansion; attention ignores unused slots. Reject mixed precision, unsupported audio projection, nonbinary masks, future-valid slots and position overflow.

Initial shapeless compilation failed on unsupported Slice inference, then stale cache-growth dimensions; an eager workaround also drifted on a strict F32 fixture. Those attempts were rejected. Fixed-capacity compilation with slice_update passes expansion, prior-state immutability and A→B→A tests; no tolerance was relaxed to accept the failed approach.

```sh
PYTHONPATH=vendor/breeze-tts UV_CACHE_DIR=/private/tmp/simo-uv-cache \
uv run --offline --project services/breeze --frozen \
  --with mlx==0.32.0 --with pytest==8.4.2 \
  python -m breeze_infer.probe_mlx_backbone \
  --model-path .models/Breeze-TTS-2 --attention sdpa --limit 3 --steps 128
```

Repeat with `--quant-bits 8`. Both reports use executable digest501715ef40900d6c7059fdc943d3a002a42934f9cb75a7b200a80ddf15b2ee3b at fork a294fe4 plus uncommitted experimental source. Three instruction-conditioned prefills,128 repeated real first-codec frames each,3 warmups/10 timings at steps0 and127. These are not natural speech trajectories or the release corpus. Timing includes audio embeddings, public state checks, layers, head and F32 CFG/evaluation; excludes sampling/depth/codec and request setup. Only the backbone step is compiled. Prefill, bridge, conversion and first evaluations are retained separately.

## Results

| Candidate | Compiled p95 across6 snapshots | Branch top1 / CFG top1 | Maximum CFG relative L2 |
|---|---|---|---|
| BF16 SDPA |14.26–14.35ms|754/768;327/384|0.07282|
| 8-bit affine SDPA |7.19–7.66ms|748/768;316/384|0.09848|

Compilation also changes accumulated numerical results: uncompiled BF16 is755/768 branch and323/384 CFG; uncompiled8-bit is750/768 and322/384, versus the compiled table above. None is guided-greedy equivalent to reference. On first128→256 expansion, compiled BF16 takes21.39ms and8-bit14.64ms; later prompt expansions benefit from already compiled capacity graphs. These are observed individual steps, not expansion p95. Corrected Torch separate-eager p95 controls are41.11–56.97ms, not the best prior SDPA implementation.

An initial one-prompt BF16 report included costly DynamicCache reconstruction inside Torch timings. Independent review identified112 extra key/value concatenations per control. Final reports construct and synchronize fresh reference caches outside timed intervals; normal continuation updates remain timed. The initial44–45ms control is superseded and must not support speedup ratios. Cache snapshots remain immutable under the inspected pinned DynamicLayer implementation.

Eight-bit covers exactly196 attention/MLP linears, group64 affine:2,818,572,288 of2,818,820,096 backbone-layer/norm bytes, packed1,497,366,528bytes. This denominator excludes audio embeddings and output head, so it is not whole-model coverage. Norms including Q/K, embeddings, head and codec remain unquantized. Four actual production matrix shapes pass paired execution tests. Kernel artifacts are the exact E-008 libmlx.dylib/metallib digests; no exports occurred.

Full fork overlay suite:113 passed, including26 depth and22 backbone tests. Tests cover unequal prefixes, adversarial padding, branch swapping, evaluated replay, full prior-state preservation, nonmultiple final cache bound, rejected masks/projection/precision and production8-bit shapes. Locked reference:65 passed, two optional MLX modules skipped. Simo Python124, knowledge5 and focused lint pass; docs86 concepts/zero errors/two pre-existing warnings. No audio, LAN, resident or audible acceptance follows from this screen. Probe exit0 means finite valid logits only. Fresh Quality health remains ready/non-busy with original7d52e5a4 runtime fingerprint.

## Artifacts and next gate

Local .artifacts/breeze-performance SHA256:

- mlx-operations.json:790edde175adc3d59dbf990300536c14e433a1c421eeebe3a8daf9aa074a519c.
- mlx-operations-attention.json:eee7c405a5e73b9f2e994a6600aa0a2e158d876656261ec7fe822b00144139f6.
- mlx-depth-eager-scale-fixed-3.json:02ce1e5308ca35df61020cac3c735194a3dee57cead542f9f8c8d785609a5b11.
- Superseded one-prompt mlx-backbone-bf16-1.json:003be36bb8c3035a9e93323e89bbf9b81143c3edbc3ee9becdf5ca99cf4bfdc5.
- mlx-backbone-bf16-3-128.json:aede29e46dcbb6d79e1398642a875b5e4235e55f3ba8cfec57ea15b69a3c18e2.
- mlx-backbone-int8-3-128.json:488ba935b56e55ce45d75f14854bb4eb794dd9c137dd9e71c86b14495d798f2a.

Next bounded gate: isolated full-utterance loop with explicit backbone-specific sampling/EOS, shared depth key progression, existing stateful codec and cancellation/cleanup. Measure actual PCM arrivals and complete-text defects before any serving or Fast promotion. Full-preview buffering still postpones playback until completion and requires a later separately tested streaming policy. Freshness2026-09-05.
