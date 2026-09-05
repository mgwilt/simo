---
type: Evidence Record
title: Isolated MLX complete-utterance performance
description: Real PCM generation with an8-bit MLX backbone/depth candidate meets the small producer throughput screen while full-system and quality gates remain open.
tags: [work, breeze, mlx, performance]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T06:40:49Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-010
  authority: evidence
  repository_paths: [vendor/breeze-tts/breeze_infer/mlx_speech.py, vendor/breeze-tts/breeze_infer/probe_mlx_speech.py, vendor/breeze-tts/tests/test_mlx_speech.py]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Isolated MLX complete-utterance performance

T-011 implements real utterance generation, not another repeated-frame microbenchmark. Torch preserves text/instruction preparation and prefill; paired MLX backbone and depth generate complete frames with explicit sampling keys. Existing PortableBreezeStreamingRuntime owns bounded delivery, per-request FP32 codec, Stop/error cleanup and inference ownership. This wrapper is not reachable from live serving. Quality remains the default; Fast remains disabled.

## Method and supported recipe

M3 Ultra512GiB; original model799624c and reference weights/locks unchanged. Torch2.9.1, Transformers4.57.3, qwen-tts0.1.1; isolated MLX/MLX-Metal0.32.0 and pytest8.4.2 overlay. Both stages CFG4, temperature0.9, top-k50, top-p1, sampling enabled; effective repetition1.0;750-iteration ceiling. BF16 activations, FP32 codec; optional affine8-bit group64 only on the previously shape-tested backbone/depth attention/MLP linears. Exclusions and kernel digests remain [E-008](E-008-mlx-depth.md)/[E-009](E-009-mlx-backbone.md). No original weights, environments, serving, identities or trust stores changed.

The backbone uses HF threshold top-k/ties and ascending cumulative top-p before reserved masking; depth uses its separate mask/probability filter. Actual EOS2051 skips depth/codec and emits all2050 sentinel; token0 remains valid audio. Truncation/empty output fails. Unsupported processors, CFG modes, reference audio, malformed text prefixes and incompatible layouts fail closed. Same-seed Torch/MLX random streams are not equivalent.

Request clock starts before preparation, includes prefill, bridges, all generation/codec work and cleanup. Arrival records are actual yielded PCM chunks, not first-code timestamps. Steady RTF uses first-to-last PCM arrival divided by audio duration after the first chunk, matching Simo's CLI definition. Total RTF remains separately reported. WAVs are created exclusively in new local evidence directories; failed/partial output never enters preview caches. Conversion/first warmup compilation are retained separately. No HTTP/browser timing in this producer probe.

```sh
PYTHONPATH=vendor/breeze-tts UV_CACHE_DIR=/private/tmp/simo-uv-cache \
uv run --offline --project services/breeze --frozen \
  --with mlx==0.32.0 --with pytest==8.4.2 \
  python -m breeze_infer.probe_mlx_speech \
  --model-path .models/Breeze-TTS-2 --quant-bits 8 \
  --audio-dir .artifacts/breeze-performance/mlx-speech-int8-short-30-audio \
  --warmups 3 --corpus .artifacts/breeze-performance/mlx-short-corpus.json \
  --seeds 42 43 44
```

Corpus exports the current Simo10-prompt constants and effective warm/thoughtful instruction. Earlier SDPA used17/29/42, so this is not an identical-seed implementation comparison. Corpus was immutable during the measured runs and before/after hashes match. Final tooling now hashes the same bytes initially parsed, closing the reviewed provenance race without changing inference. Root ran measurements; independent held-source review is [R-108](../results/R-108.md).

## Completed short results

| Screen | First PCM | Steady RTF | Completion/defect screen |
|---|---|---|---|
| BF16,3 instructions,seed42,1 warmup | retained per sample |1.076–1.081|3/3 EOS; local-ASR flags train→trade once |
|8-bit,same3 instructions/seed/warmup |0.264–0.374s|0.679–0.693|3/3 EOS;0/17 ASR word errors |
|8-bit,10 prompts×3 seeds,3 warmups |p950.508s|p950.687; max0.690|30/30 EOS;1/294 ASR word errors |
|8-bit,2 long prompts×seeds17/29/42,3 warmups |0.298–0.409s|0.6813–0.6845|6/6 EOS; full recognized endings |

The30-sample run produces1528 codec frames/122.24s audio. p95 total RTF0.787; first-code/PCM and output duration stay distinct. ASR flags a possible extra trailing "and" after the correction prompt at seed44. This is a defect flag requiring listening, not proof of either a real acoustic defect or harmless recognition error. Automatic WER0.34% does not establish instruction/perceptual acceptance. BF16/8-bit durations differ; do not infer a pure implementation speedup ratio from complete-utterance wall times.

Long run: use the same command with mlx-long-corpus.json, a new audio directory, and seeds17/29/42. Six samples produce2149 frames/171.92s audio, individual duration26.96–30.40s; p95 steadyRTF0.68448 and firstPCM0.40865s. Maximum local inter-chunk gap78.43ms is below the80ms audio per chunk, but not LAN/underrun evidence. Raw ASR WER is6/396 (1.52%); all six differences are splitting "tradeoffs" into two tokens. Case/punctuation/spacing-normalized alphanumeric transcripts match all six prompts exactly, including their final sentences. Preserve the raw score; this is complete-text screening, not instruction or audible acceptance.

Initial attempt failed before generation because the strict config guard did not account for duplicated depth_decoder_top_p metadata. Fixed with an exact supported-field list and duplicate-versus-effective settings consistency check; no generation recipe changed. Empty first artifact directory/JSON are failed-attempt evidence, not accepted measurements.

Full overlay suite148 tests passes, including35 speech tests for filtering boundaries, EOS/codec0, key/replay, complete/failed/limited output, cancellation/retry, unsupported settings, text validation and exclusive evidence writes. Prior-state/backbone/depth tests remain included. Locked reference65 passes/three optional skips; Simo Python124, knowledge5, focused lint and docs91 concepts/zero errors/two pre-existing warnings pass. All GPU/ASR probes completed. Resident, matched listening, actual LAN playback and observed device underruns remain unverified. Next use common17/29/42 short/long cohorts before/with resident Simo models, and production cancellation/retry, then an independently gated LAN playback experiment.

## Artifact identities

Local .artifacts/breeze-performance SHA256:

- mlx-speech-int8-3-v2.json:8b71c4ef330460a234518e6ee5684b1c7c05fb13136911b138e5af9f1d5cd0ad.
- mlx-speech-bf16-3.json:d447cccdaebc78293f0c8e049e7bc59a0c3bc352643ca5a66ed8c7923672c9cb.
- mlx-speech-int8-3-asr.json:c1fcc9649adca7fdf71c226c47851d0eedb6cec25133664a615fd75c84de6f9b.
- mlx-speech-int8-short-30.json:b5f62fa1256c999c997dbe6fa5c6f2745e9ef4bb03e81fc094185bd10a1e959a.
- mlx-speech-short-and-bf16-asr.json:d4319fd42a103b5104f56aab89acb8eda772416683e38547bf8d821b351c00e9.
- mlx-speech-int8-long-6.json:f2cedefa809c6ba8c1199b9efa5c197dd904d765cab79b2bd8051c5b9668959b.
- mlx-speech-int8-long-6-asr.json:3f592ea0f433a47c1cf4c7bbdac59e6ee52c308cb138a87f6600e1fd725b5bd9.
- mlx-short-corpus.json:99f8b8695ba921a7dca5ef9f62223fe0887352d929d2434868688a6f090d22d1.
- mlx-long-corpus.json:6c11441b3b50d7a573f2c4caef167d2048d98c856999ab1e611e5c33a1bf3f77.

Three-instruction reports use executable a348c64023e0197d777220b5cebe527759f552632575a3fd98ba22129915c42f; full short/long use d2499df658f4be8b9627eb0628f33608de15708e1be0b3bc71aa4e1754648c1e. Final corpus-identity fix yields8cc3f875eae7897a8451248bf7cf93fc93ca57f8202ab045acbb7de965ca690d, independently reviewed and regression-tested; inference code unchanged from the full runs. Owned fork a294fe4 plus local experimental files; parent2ffe040 with preserved prior changes. No commits/pushes. Proves local uncached producer performance and bounded lifecycle/defect checks. Does not prove reference numerical identity, voice adherence, HTTP/tap-to-playback, resident performance, zero audible underruns, CUDA or Fast release. Freshness2026-09-05; autonomous goal remains active. Quality health freshly remains ready/non-busy with original7d52e5a4 fingerprint.
