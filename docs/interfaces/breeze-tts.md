---
type: Interface Contract
title: Breeze-TTS-2 boundary
description: Defines Simo's pinned loopback Breeze-TTS-2 service, PCM contract, Apple Silicon compatibility layer, capacity, and licensing boundary.
tags: [interface, breeze, tts, audio, mps, licensing]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T09:52:00Z }
stale_after: 2026-12-01
sources:
  - id: breeze-model
    resource: https://huggingface.co/BreezeBlue/Breeze-TTS-2
    title: Breeze-TTS-2 model card
  - id: breeze-upstream
    resource: https://github.com/breezeblue-ai/breeze-tts
    title: Breeze-TTS-2 reference source
  - id: breeze-mps-fork
    resource: ../../vendor/breeze-tts
    title: Simo-owned Breeze-TTS-2 MPS fork revision
  - id: breeze-license
    resource: https://huggingface.co/BreezeBlue/Breeze-TTS-2/blob/main/LICENSE
    title: Breeze-TTS-2 model license
  - id: simo-breeze-service
    resource: ../../services/breeze/serve.py
    title: Simo Breeze Apple Silicon service launcher
  - id: simo-breeze-client
    resource: ../../python/simo/inference.py
    title: Simo Breeze PCM synthesizer
  - id: simo-https-benchmark
    resource: ../../python/simo/breeze_benchmark.py
    title: Fixed-corpus HTTPS measurement boundary
simo:
  profile_version: 1
  stable_id: DOC-0008
  authority: interface
  repository_paths: [.gitmodules, vendor/breeze-tts, services/breeze, python/simo/breeze.py, python/simo/inference.py, python/simo/config.py, python/simo/livekit_runtime.py, scripts/setup_models.py, tests/python]
  owner: codex/gpt-5.6-sol
---
# Breeze-TTS-2 boundary

## Pinned deployment

Simo's submodule pins the owned `mgwilt/breeze-tts-mps` fork at published revision `78a79bbe7996f88766ee1885140909ca696c7055` on `simo-apple-silicon`, descended from integration `a38d7d1` and official upstream `0072588a517f54a3a91d8f566be91cce74b64d13`. The model remains `BreezeBlue/Breeze-TTS-2` at `799624c0b4a1daa8db6d28bbd9850043c0270734`. Model download remains opt-in. The model is approximately7.7GB and official deployment targets Linux/CUDA; Apple Silicon support is a Simo-owned boundary, not an upstream claim.[^breeze-model][^breeze-upstream][^breeze-mps-fork]

`services/breeze` owns a separate unchanged locked Python environment: PyTorch2.9.1, Transformers4.57.3 and qwen-tts0.1.1. It binds to `127.0.0.1:7860`. The quality path uses MPS BF16, eager attention, cached batched depth CFG and a generated-code-frame callback feeding stateful FP32 codec decoding one frame at a time. A single worker owns model and codec state; bounded queues connect it to HTTP without full-utterance buffering. `--engine reference` retains the original full-generation/offline-codec path. Current performance work and exact source state are tracked in the [dedicated project](../work/W-20260904-breeze-mps-performance/), separately from historical integration.[^simo-breeze-service]

## Request and response

Default endpoint: `http://127.0.0.1:7860/v1/audio/speech`

The client sends form fields `text`, `instruction`, `cfg_scale`, and `seed`. Text/instruction must be non-empty, at most4000/2000 characters and within token capacity; CFG must be finite and positive. An optional `X-Breeze-Runtime` pins the request to a health fingerprint; mismatch returns409. Simo does not expose reference-audio cloning.

Successful responses are raw mono16-bit little-endian PCM. `X-Sample-Rate` must be `24000` and `X-Sample-Format` must be `s16le`; incomplete samples, metadata mismatch, non-200 responses and failures abort the utterance. The client uses non-coalescing reads and bounded queues. Disconnect shuts down its socket and propagates cancellation to the frame worker; inference ownership is retained until generation and codec cleanup finish. Generation without EOS fails rather than claiming complete output.[^simo-breeze-client]

One inference request is allowed; concurrent requests return409. Health includes readiness, busy state, source/model content fingerprints, dependency versions, effective settings, startup/stage timings and quantization coverage. It excludes prompts, audio and credentials. Failed codec cleanup makes the runtime unavailable until restart.

## Runtime profiles and rollback

Operator-only `--performance-mode quality|fast` never changes stored profiles or adds a UI selector. Quality is default, uses requested CFG and unchanged sampling parameters. Fast currently fails closed: no recipe has passed release/listening gates. Experimental `--attention sdpa`, `--depth-cache static|compiled` and `--quantization int8|int4` are identified as candidates in health. Quantization changes only eligible backbone/depth layer linears in memory; original weights and the dependency lock remain the rollback. Compilation and quantization cannot currently be combined.

The separate operator-only `--experimental-recipe mlx-int8-v1` selects an unaccepted MLX candidate, not Quality or Fast. It requires a different loopback port, MPS streaming and unchanged reference flags. Torch retains text preparation/eager BF16 prefill; compiled MLX backbone/depth use BF16 activations and affine8-bit group64 linears, excluding embeddings, norms, projectors, custom/output heads and FP32 codec. This recipe uses the isolated MLX/MLX-Metal0.32.0 overlay without changing the reference lock. Dependency and Metal artifact identities must match the tested recipe. Default Quality imports no MLX candidate.[^simo-breeze-service]

The MLX candidate accepts only explicit CFG4, instruction-only input and uint32 seeds. It validates both prepared prefixes against actual cache capacity before streaming headers or codec work. Unsupported CFG/reference behavior fails rather than silently changing the request. MLX's explicit seed key is not Torch-seed equivalence. Health and response fingerprints derive from actual loaded settings, quantization coverage/inventory digests, source/model contents, dependencies and Metal artifacts; `performance_mode=experimental` and `release_accepted=false` remain explicit. The unchanged portable codec runtime owns cancellation and inference serialization. Current HTTP/TLS evidence and limits are in [E-012](../work/W-20260904-breeze-mps-performance/evidence/E-012-experimental-serving.md); the implementation is published through the pinned fork revision.[^simo-breeze-service]

The isolated HTTPS preview site may independently opt into `mlx-stream-v1` for an operator-selected exact runtime fingerprint. Site health/listing and PCM/WAV headers declare that playback policy; it is not a change to the inference fingerprint or a Fast promotion. The player uses a640ms reserve, two-second in-flight PCM credit bound and120-second response cap. Quality/default/unknown policies retain complete-clip buffering. Early experimental playback can precede a late error, which clears queued audio and cannot commit a partial cache. Startup and rollback are in [LAN operations](../operations/lan-voice-site.md#isolated-experimental-mlx-previews); [E-013](../work/W-20260904-breeze-mps-performance/evidence/E-013-progressive-playback.md) pins implementation/replay/served-policy proof and physical-playback limits.

New aliases use `simo.runtime-profile.v2` with Breeze backend, model/revision, voice-design text, instruction, CFG scale, and seed. Profile versions are immutable. Legacy v1 profiles continue to resolve to the pinned Qwen MLX-Audio model and voice. `SIMO_TTS_BACKEND=qwen` explicitly overrides the active profile's TTS selection for an operator rollback in the new process without mutating stored history.

The isolated site's startup-only `--enable-benchmarks` requires exact streaming selection and adds server-owned short/long corpus routes, absent by default. Only fixed indices, known instruction IDs and strict uint32 seeds are accepted in bounded JSON; manifest/runtime headers bind requests. Responses declare BYPASS/no-store, actual request ID, runtime/manifest/policy and PCM format. Matching final metrics require completed/EOS/noncancelled status and exact sample/frame totals. These routes never touch preview caches or expose arbitrary text/reference inputs, and do not broaden the normal synthesizer's loopback allowlist. Source/build changes invalidate the manifest until site restart.[^simo-https-benchmark]

CLI schema3 measurements retain the complete schedule, warmups, request-bound metrics, WAV hashes, arrivals and failures in exclusive evidence directories. Unpaced HTTPS throughput is separate from simulated player replay and physical playback. [E-015](../work/W-20260904-breeze-mps-performance/evidence/E-015-https-corpus-residency.md) records252 timed outputs with p95steadyRTF0.685–0.698, exact control/resident PCM and zero modeled playback gaps; seven non-segmentation ASR candidates, matched listening and actual-device gates remain unresolved. Fast remains disabled.[^simo-https-benchmark]

## Performance and rights boundary

Historical identities E-007 measured p95 first PCM71.873s and RTF13.511; that evidence is unchanged. The fresh baseline and current screens are in the [performance evidence](../work/W-20260904-breeze-mps-performance/evidence/E-002-screening.md). Release requires warm uncached p95 tap-to-playback<=2s, steady-state RTF<=0.8 and zero observed long-suite underruns, plus quality/listening checks. RTF1.5 is slower than playback and is no longer a realtime target. Earlier PCM does not establish uninterrupted audible speech; current candidates remain evaluation infrastructure.

The source repository is Apache-2.0, but the distributed model has its own license restricting use to personal, academic, research, education, and other non-commercial purposes. Simo's integration does not broaden those rights; operators must review the model license before use.[^breeze-license]

[^breeze-model]: Breeze-TTS-2 model card, verified 2026-09-02 for model identity, size, audio contract, and official hardware guidance.
[^breeze-upstream]: Official Breeze-TTS-2 source at base revision `0072588a517f54a3a91d8f566be91cce74b64d13`, verified 2026-09-02.
[^breeze-mps-fork]: Published owned-fork revision `78a79bbe7996f88766ee1885140909ca696c7055`, with the MLX implementation at parent `05129be2`, 200 fork tests, and bounded MPS production checks. Earlier parents `9ab3fb9` and `a294fe4` preserve incremental-streaming and standalone-health history. Remote branch verification is recorded in `W-20260904-breeze-mps-performance#E-023`.
[^breeze-license]: Breeze-TTS-2 model license, verified 2026-09-02; this documentation is not legal advice.
[^simo-breeze-service]: `services/breeze/serve.py` and its isolated lockfile; observed fork-native MPS load and synthesis are recorded in `W-20260802-conversational-identities#E-007`.
[^simo-breeze-client]: `python/simo/inference.py`, `python/simo/livekit_runtime.py`, and focused tests in the implementation based on `f5a039f`.
[^simo-https-benchmark]: `python/simo/breeze_benchmark.py`, experimental site, request-scoped client metadata, CLI and tests; held source/admission [E-014](../work/W-20260904-breeze-mps-performance/evidence/E-014-https-benchmark-contract.md) and measured [E-015](../work/W-20260904-breeze-mps-performance/evidence/E-015-https-corpus-residency.md), verified2026-09-05. No model/physical-quality promotion.
