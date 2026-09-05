---
type: Evidence Record
title: Reproducible README performance charts
description: Source-audited historical and matched precision charts from recorded Breeze performance evidence.
tags: [work, performance, documentation, benchmarks]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T19:34:00Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-024
  authority: evidence
  repository_paths: [README.md, benchmarks/breeze, scripts/render_breeze_benchmarks.py, tests/python/test_breeze_charts.py]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Reproducible README performance charts

T-024/A-010, L-024/root integration owner. User requested technical README charts/specs including the owned MPS fork and improvement over recorded history, with Flecs copy removed. Implemented reporting only against Simo base a5ac3fd7a7acc84a6749610147646778da70f6f7. Fork gitlink/source remains78a79bbe7996f88766ee1885140909ca696c7055; no engine, dependency, runtime, service, profile, model/audio/browser, inference or publication change. Unrelated untracked :memory:.ses preserved.

## Artifacts and claims

[Benchmark methods](../../../../benchmarks/breeze/README.md), [scalar data](../../../../benchmarks/breeze/measurements.json), [cohort table](../../../../benchmarks/breeze/results.md) and two generated SVGs accompany the [README](../../../../README.md). The standard-library exporter retains397 timed rows/18 selected cohorts plus12 separate startup requests, original receipt paths/bytes/SHA256, available model/source/runtime/settings/dependency/PCM identities and all precision ASR flags. Missing baseline seed/runtime/clock fields are not invented. Full local receipts/audio/model weights are not copied into Git.

- History: reference→cached streaming→MPS SDPA→MLX int8 producer→uncached HTTPS. Recorded p95totalRTF9.954→7.013→3.442→0.799→0.800; p95firstPCM49.165→0.809→0.665→0.393→0.407s. Counts/warmups, absent early clocks, receipt versus start timestamps, changed boundaries/RNG/durations and ordinal spacing are explicit. Not an isolated speedup attribution.
- Matched four-arm precision:18 timed+3 warmups/arm, inputs/settings fixed, p95steady1.088/1.008/0.770/0.688. Int8/int8 improves normalized p95steady36.7% versus BF16, with3/5/6/7 ASR word errors of189 reference words. Sampled outputs differ; no perceptual promotion.
- Serving:252 uncached same-host HTTPS rows across10 control/idle-resident cohorts; p95steady range0.685–0.698, firstPCM0.312–0.428s,126 exact timed PCM pairs, zero modeled player underruns. Startup ranges remain separate, not p95/disk-cold/physical onset.
- Specs: hybrid Torch/MLX, paired CFG4, compiled cached generation,280 group64 int8 linear weights, selected packed-weight byte reduction46.875% (not process memory), FP32 actual Qwen3 codec and precise pinned dependencies. [R-135](../results/R-135.md)/[R-136](../results/R-136.md) record independent source/measurement audits.

## Verification

Root commands: `uv run --frozen python scripts/render_breeze_benchmarks.py --extract --check` reproduces all four generated products from the original local receipts; ordinary `--check` needs only checked-in scalars. Eleven focused CPU tests pass for nearest-rank p95/invalid values,397-row integrity and hashes, missing baseline fields, input matching/output differences, ASR counts, selected-weight bytes, uncached/resident pairs, separate startup identity, exact generated XML, README links/Flecs removal and non-mutating stale-product detection.

Configured parent Ruff/format (python/simo, tests/python, scripts;106 files), ty and BasedPyright pass. A broader exploratory `ruff check .` reports four existing services/breeze/serve.py security/style diagnostics outside the configured Lefthook targets; left unchanged. No fork/web/native/inference gates are rerun for this reporting-only change. Root full-canvas primitive raster QA passes text bounds and visual inspection for both charts; macOS Quick Look's cropped thumbnails were discarded as proof. No Safari, browser or CUA was used.

Independent [R-137](../results/R-137.md) passes: all18 raw hashes/397 rows,126 paired outputs,280 individual weight records and exact percentages verified;11 tests and4-product reconstruction independently pass. Documentation168 concepts/zero errors/four existing advisory categories, five knowledge tests and git diff --check pass. L-024 released2026-09-05T19:37Z; A-010 reporting complete locally without commits/pushes. Full Fast/perceptual/physical release gates remain open regardless of this reporting slice.

## Held artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| measurements.json | c920d96578ace2052305eec3b3ea053f69693c71302b66d4b29b2af427aeb37b |
| progression.svg | 6e9f737ca2906d2fc1fbd61e9c026f8f7276389178783161e848e2fdf6e6122c |
| precision.svg | 421462e136d95d1127c08a881f5817046f4396945392c4e1e842352c1de36249 |
| results.md | 69ace7688f419eaaa1a033b9c1b00b608603ce970dd2cdbcf7508b0698c69e74 |
| renderer | 4d31c5cf6634ddacc6a3d242229aba374a221646ce9a5d1b86af3f6141e4b991 |

Freshness: source-audited recorded receipts on this host,2026-09-05; these charts are not new performance runs or a current server-health attestation.
