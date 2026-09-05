---
type: Work Evidence
title: Flagged speech quality localization
description: Hash-bound full-clip recognition diagnostics and exact-case Quality comparisons retain unresolved speech-quality gates.
tags: [work, breeze, quality, inference]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T10:28:41Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-016
  authority: coordination
  repository_paths: [scripts/triage_breeze_audio.py, tests/python/test_breeze_quality.py, docs/work/W-20260904-breeze-mps-performance]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Flagged speech quality localization

T-016/A-007 under L-013, root sole writer/GPU owner. Starting evidence [E-015](E-015-https-corpus-residency.md) and independent [R-117](../results/R-117.md). No model, codec, serving source, player, assets, lock, STT adapter or identity changes. Quality remains default and Fast disabled. All audio is existing synthetic test text; no microphone, playback, browser/computer use, download or external transfer.

## Full-clip recognition diagnostic

The fixed manifest selects all seven non-segmentation flags plus six unique default-instruction counterparts:13 full clips,1,355,520 samples/56.48s. Different instructions are context, not matched reference-model controls. All ten original flags remain recorded, including three long-utterance tradeoffs segmentation candidates. Original WAV/PCM/report/runtime/settings hashes are verified before use; no cropping, normalization, seed or instruction substitution.

One run compares stream-local, stream-original-attention, offline-same-array and offline-file. The first three share the same float32 Simo-resampled array; native file transcription uses the installed FFmpeg path and is separately labeled. All52 transcripts exactly reproduce the original screen. All seven flags persist; all six default counterparts remain clean. All26 before/after-context token records match; all tokens are draft, already included, with zero raw audio remainder. Full mel shapes are measured, not actual encoded feature lengths. There is no observed context-exit flush loss, and no tested recognition path removes the flags.

| Case (one-based prompt) | Seeds | Persistent recognition difference |
|---|---|---|
| warm-companion p6 |29,42| initial A omitted |
| warm-companion p10 |29| answer→answers |
| bright-guide p6 |17| A→The |
| bright-guide p7 |29| The→But |
| bright-guide p10 |42| answer→answers |
| grounded-mentor p6 |17| manageable→manager |

These arms share Parakeet and cannot adjudicate TTS versus recognizer error. Cross-arm token timing/confidence differs despite identical text. Recognizer marker revision ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15 matches; weight digest is explicitly unverified. Dependencies: parakeet-mlx0.5.2, mlx/Metal0.32.0, numpy2.4.6. Nine loaded-source/marker/lock hashes are recorded. Native FFmpeg output/binary identity is not recorded, and diagnostic wall times are not comparable performance benchmarks. [R-119](../results/R-119.md)/[R-120](../results/R-120.md) independently review source/API and actual evidence.

Command, using existing caches, first without and then with --diagnose into distinct exclusive directories:

```sh
UV_CACHE_DIR=/private/tmp/simo-uv-cache TIKTOKEN_CACHE_DIR=.cache/tiktoken uv run --frozen python scripts/triage_breeze_audio.py --output-dir .artifacts/breeze-performance/mlx-quality-triage-v1-diagnostic --diagnose
```

Session20296 exited0. Diagnostic body elapsed4.576s is diagnostic-only; no latency claim. Original held source0fb323be50184efefb3f66282a2dd8629ce523c7291a8e4148803cae3ed2bf70; original tests d7df6d85e1d27e8e460889bcc7f2af57f973ab0f108d65d70a769663f1ba4aab. Both original manifests equal e009b51b987a10568a85ff62019323e5df3e04c1b9204fb7df7f620c9ccf32ff; diagnostic8e814b068692d8077b40b547b7f3c2101eacea30efe44e0f221627f34c839bdb. Local artifact directory is .artifacts/breeze-performance/mlx-quality-triage-v1-diagnostic; raw audio remains in the original E-015 directories.

## Same-input Quality controls

The explicit --quality-controls extension requests exactly the seven flagged text/full-instruction/nominal-seed cases at CFG4 through unchanged idle127.0.0.1:7860, binds actual response/request/completed metrics and retains partial failures. No hidden warmups/retries; this is content diagnosis, not a latency benchmark or isolated quantization comparison. Cross-backend random streams differ even at equal seed. Do not promote quality from ASR agreement or request labels.

Independent mlx_mapping review in [R-121](../results/R-121.md) prompted explicit cancellation-evidence retention and pre-request client/health/validator/lock source hashes plus timestamps. A bounded five-read busy-state completion poll is conservative, not evidence of a demonstrated race. Nine CPU fixtures cover exact selection/PCM/no overwrite, partial-stop behavior, identity/EOS/count failures, stream cleanup/cancellation and manifest roundtrip. Full parent156 tests and all static checks pass at held source78fff4cee68d23a390d6b1fe7099cbeec1b4fae44129d5cf7d81a0dd9a80ac8c/tests f084a8fb3380add9e5ea25b7cd8e21c1c1e5d0fd7386d8a11cf5355cfc6b6408.

Preserved failed preflight: first --quality-controls launch (source a7a1d3c0…) compared in-memory key tuples against JSON lists and stopped before controls.json, network or model calls. Fixed both manifest key fields to JSON-native lists; regression and independent rebuild prove unchanged serialized e009b51b… and exact original-manifest equality. No synthesis sample was rejected or retried. Initial directory mlx-quality-triage-v1-quality-controls retains initialization-failure.json SHA2e6e2b6de0351db7ecc04e7ffe128122ae548153369eca425d874713b3f473f0. Corrected run uses fresh mlx-quality-triage-v1-quality-controls-r2/session44793 and exited0. Original52-result recognition evidence remains unchanged.

Exactly seven unique actual request IDs completed with EOS/not-cancelled/idle health and matching codec/sample totals:675,840 full PCM samples/28.16s. Each used one post-EOF health read; no busy-state polling was needed. Both before/after runtime fingerprints equal the unchanged Quality7d52e5a4dfa21507711928e32a26a758ecca1fb93871e8c9afefedd6dc05c96b, which records model799624c/contentaebc74ea…, unquantized TorchBF16/eager/dynamic cached CFG and retained dependency versions. No warmups or synthesis retries were made. The118.068s control batch is not a matched throughput benchmark.

All28 control recognitions complete: six cases have zero word errors in each arm; warm-companion p6/seed42 omits initial A in all four (native-file capitalization differs). Raw word errors are1/74 per arm versus7/74 for the corresponding original MLX clips. The shared case is not cleared, and six cleaner reference transcripts do not establish quantization causality: these are different sampled outputs/backends, not paired random draws. All original flags remain unresolved acoustic-quality candidates. Next bounded comparison is compiled MLX BF16 versus int8 with the same existing probe, six exact text/instruction pairs×17/29/42, preserving all18 outputs per candidate and3 warmups. First verify the int8 probe reproduces the original behavior despite its different PCM16 encoder; no settings/seed cherry-picking, serving change or Fast promotion.

Artifacts in .artifacts/breeze-performance/mlx-quality-triage-v1-quality-controls-r2:

| Artifact | SHA256 |
|---|---|
| controls.json |e0f7c4ec1dbf455fda5810781ac5d399dd1e4f580f8effbcfeb4f9e015af970f|
| diagnostic.json |c1b643ce888864e195966b9ebbfe60ab554c7cd67b618565436c45088ad2352c|
| manifest.json |e009b51b987a10568a85ff62019323e5df3e04c1b9204fb7df7f620c9ccf32ff|

Controls retain full requests, source and runtime health identities, actual IDs, WAV/PCM hashes, elapsed diagnostics and complete metrics. ASR report binds controls.json and eleven recognizer/client/source hashes; original9-source recognition report stays historical. No weight rehash, physical onset, instruction listening or actual LAN-device underrun acceptance is asserted.

Other development failures were confined to fixture typing/lint and a docs invocation without TIKTOKEN_CACHE_DIR, which failed DNS. Corrected static checks and docs with the existing tokenizer cache pass without a download. No failed invocation is release evidence.
