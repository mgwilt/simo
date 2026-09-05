# Breeze performance evidence

The [Simo README](../../README.md#breeze-tts-performance-on-apple-silicon) reports recorded
engineering results for Breeze-TTS-2 on the development M3 Ultra. This directory publishes a
portable scalar extract and reproducible SVGs; it does not rerun inference or promote Fast.

## Reproduce the figures

Python 3.11+ standard library only; run from the repository root:

```sh
python3 scripts/render_breeze_benchmarks.py
python3 scripts/render_breeze_benchmarks.py --check
python3 -m unittest discover -s tests/python -p test_breeze_charts.py -v
```

[measurements.json](measurements.json) contains all 397 timed rows from the 18 selected cohorts,
plus the 12 requests in the separate startup study. [results.md](results.md) and both SVGs are
generated from it. The JSON retains available prompt/instruction/seed, duration, timing, codec
frame count, completion state, PCM hash, effective settings and source/runtime/model/dependency
identities. Missing fields remain missing or null, never imputed. Per-weight inventory lists are
compacted to their count and recorded byte totals; full receipts remain the source of authority.

Every source receipt has a repository-relative local artifact path, byte size and SHA-256.
Original reports, audio and models are not part of this public data extract. If those receipts
are available locally, verify a fresh extraction with:

```sh
python3 scripts/render_breeze_benchmarks.py --extract --check
```

Omit `--check` to deliberately refresh the extract. This reads existing artifacts, not services.
It retains every timed row in each selected cohort, including ASR flags; it does not filter to
successful or fast samples. Synthetic benchmark text is included, not conversation history.

## Metrics and comparison limits

- **Total RTF** = request/producer wall time through completion / generated audio duration.
- **Steady-state RTF** = elapsed time after first PCM / remaining audio duration after the first
  chunk. It is a throughput estimate, not interchangeable with total RTF. Original measurements
  are retained verbatim; the locked reference has no separately measured steady-state metric.
- **First PCM** = first chunk observed at the named producer/client boundary. It excludes model
  process startup in the warm cohorts and does not measure browser scheduling or speaker onset.
- **p95** is nearest rank: sorted sample at `ceil(0.95 × n)`, excluding warmups. With 3, 6, 10 or
  18 samples it is the maximum; with 30 it is the 29th value. No confidence intervals or
  population-level guarantees are implied. Per-cohort p95 ranges are not pooled percentiles.
- **History chart:** selected implementation milestones, not an exhaustive experiment log or
  causal ablation. Short eager n=3 is visibly marked. MPS SDPA also includes direct output-head
  indexing, not just an attention switch. Failed native MPS int8/int4 and compiled-depth screens
  remain in [E-002](../../docs/work/W-20260904-breeze-mps-performance/evidence/E-002-screening.md)
  and the Work Plan; the chart does not imply every experiment improved performance.
- **Chronology:** the first two raw receipts have no wall clock. SDPA uses the report's
  `recorded_at` field (00:31 UTC Sep 5); later MLX points use run-start clocks. The E-002 header
  predates its SDPA addition and is not a run timestamp. X spacing is ordinal, not elapsed time.
- **Matching:** SDPA30, MLX producer30 and HTTPS control-short30 use the same prompt/instruction/
  seed cases, but changed execution, RNG streams and generated durations prevent an identical-output
  speedup claim. The four-arm precision comparison changes weight precision while holding inputs
  and settings fixed; output durations still differ (BF16 69.76 s versus int8 75.92 s).
- **ASR:** the precision chart includes summed word-edit counts against 189 reference words per
  arm, measured by Parakeet. These unadjudicated flags can reflect TTS or recognizer behavior and
  do not establish intelligibility, instruction adherence or perceptual equivalence.
- **Serving envelope:** all ten HTTPS cohorts bypass completed-preview caches. Six long cases
  per condition cover two prompts × three seeds; short and voice cohorts each contain ten prompts
  × three seeds. The resident condition loads idle STT/LLM weights, not overlapping inference.
  Zero underruns refers to recorded-arrival player replay with 640 ms reserve, 2 s credit budget
  and a 120 s total cap—not real mobile Wi-Fi, speakers or an accepted latency/quality gate.
- **Startup:** three fresh process launches with one first-use plus three warm requests each;
  observed ranges only. This does not flush OS/filesystem caches. Its runtime fingerprint differs
  from the earlier HTTPS cohort; do not merge their timing populations.

## Source map

| Published data | Recorded evidence | Scope |
| --- | --- | --- |
| `reference`, `cached`, `sdpa` | [E-002](../../docs/work/W-20260904-breeze-mps-performance/evidence/E-002-screening.md) | Locked BF16 MPS → cached streaming → SDPA; raw baseline lacks runtime identity/seed fields, which E-002 reports separately |
| `mlx` | [E-011](../../docs/work/W-20260904-breeze-mps-performance/evidence/E-011-mlx-resident-lifecycle.md) | Matched short producer, int8 backbone/depth, CFG4 |
| `https-*` | [E-015](../../docs/work/W-20260904-breeze-mps-performance/evidence/E-015-https-corpus-residency.md) | 252 timed outputs, 126 control/resident pairs, player replay and quality-screen limits |
| `precision-*` | [E-018](../../docs/work/W-20260904-breeze-mps-performance/evidence/E-018-component-precision.md) | 72 timed outputs across four arms; 280 int8 linear-weight inventory and ASR flags |
| `startup` | [E-020](../../docs/work/W-20260904-breeze-mps-performance/evidence/E-020-process-startup.md) | Three fresh launches, 12 complete requests, independent startup runtime identity |

The raw MPS reference is attributed by E-002 to model revision `799624c`, CFG4 and the locked
environment. Its JSON does not itself prove the full source/settings identity; this provenance
gap is preserved. Source revisions alone may describe a dirty development base: use the recorded
source digest and effective settings as well, rather than substituting the current fork commit.

Implementation specs are source-verified against the
[pinned fork](https://github.com/mgwilt/breeze-tts-mps/tree/78a79bbe7996f88766ee1885140909ca696c7055/breeze_infer):
`experimental.py` owns recipe/dependency/Metal hashes, `mlx_speech.py` the hybrid prefill boundary,
`mlx_backbone.py` and `mlx_depth.py` the paired compiled caches and precision, `runtime.py` the
actual Qwen3 tokenizer loading, and `portable_runtime.py` the codec/queue lifecycle. Transformer
geometry is from the pinned model's nested `config.json`, not its stale top-level codec descriptor.
Selected quantized-weight bytes are not whole-model size or peak memory: Torch weights remain
resident. No CUDA, smaller-device, concurrent-model or physical playback validation is claimed.
