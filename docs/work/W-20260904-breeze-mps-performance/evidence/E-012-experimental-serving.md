---
type: Evidence Record
title: Experimental MLX serving and isolated LAN previews
description: Actual fingerprint-bound HTTP and TLS audio, cancellation, seed reuse and preview isolation without Fast promotion.
tags: [work, breeze, mlx, performance, lan]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T07:53:18Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-012
  authority: evidence
  repository_paths: [vendor/breeze-tts, services/breeze/serve.py, python/simo, web, tests/python]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Experimental MLX serving and isolated LAN previews

T-013 implements D-014/D-015's explicit experimental mlx-int8-v1 HTTP service and preview-only HTTPS site. It preserves the running Quality service, normal UI assets, reference environment/weights and Fast rejection. This is an unaccepted evaluation route, not a new identity or release mode.

## Implementation and identity

Fork API retains the Torch reference model for input preparation, validates explicit CFG4/instruction-only/uint32 seeds and both prepared prefix capacities before headers/codec, then forwards the seed into the MLX candidate. The actual PortableBreezeStreamingRuntime owns generation, codec and cancellation. Default Quality does not import the MLX candidate. The versioned registry requires tested dependencies/Metal artifacts and fingerprints actual loaded settings, not only launcher flags.

Same M3 Ultra512GB/macOS26.5.2 and original model799624c as E-011. Full service startup rehash confirms model content aebc74eac29ac4729fdf0f8c4d3870c1d8cf4efb72e4e24e9316accaa386462d. Torch2.9.1/Transformers4.57.3/qwen-tts0.1.1 reference lock remains unchanged; existing isolated overlay adds MLX/MLX-Metal0.32.0. Torch eager BF16 text/prefill, compiled MLX BF16 backbone/depth, affine8-bit group64 linears, actual FP32 codec,128-frame cache growth/4096 maximum positions. CFG4, temperature0.9/top-k50/top-p1,750-step limit; explicit MLX keys and stage-specific filters are recorded, not Torch-seed equivalence.

Actual coverage:196 backbone linears,2,818,572,288/2,818,820,096 original bytes,1,497,366,528 packed bytes;84 depth linears,666,894,336/868,560,896 original bytes,354,287,616 packed bytes. Embeddings/norms/projectors/custom-output heads/codec excluded. Health retains full-inventory digests efe1649c…/c8c0e4b8… and pinned dylib1876795e…/metallib1518c088…; complete hashes are in the retained health report and E-008/E-009. Health is about2.6KB, below the65,536-byte client bound.

Resolved runtime fingerprint f0cac89f955ee07d3f1b1bfac9d2cd8f5a2e1be5dcdb8ae4be828c66cdb24acd; service executable digest d4ba5fd38b69b2f1448e8f5c80ddf13ef07da76c281fc532f7df476417e7c273. Recipe reports performance_mode=experimental/release_accepted=false. Startup load_s3.849 excludes the preceding full weight hash and process startup. First-use HTTP warmup firstPCM1.015s, wall2.735s, audio2.48s is retained separately; it is not an OS-cold benchmark.

## Actual HTTP and TLS checks

The candidate binds only127.0.0.1:7861. Eleven real invalid-form/multipart/stale-fingerprint requests return expected400/409/422 statuses before any runtime request: negative/oversized/fractional/boolean seeds, unsupported CFG, reference text/audio, blank/oversized text, oversized instruction and stale identity. Lock returns free; last generation metrics remain unchanged.

One-prompt HTTP seed17/29/17 screen: all EOS/completed, firstPCM0.278–0.305s and steadyRTF0.686–0.692. Seed17 PCM repeats exactly; seed29 differs. TotalRTF0.777–0.808 is separately recorded. This is a small transport screen, not the required30-case release suite. Diagnostic probe WAVs round float samples whereas the preserved HTTP conversion truncates; no cross-format byte-equivalence claim follows.

Two additional actual HTTP trials disconnect immediately after headers/before reading PCM and after first PCM. Both report cancelled/not-completed; lock cleanup is observed in59.96/65.28ms, including polling overhead. The second trial rejects a competing request with409. Immediate retries complete and match the original seed17 PCM. All successful response X-Breeze-Runtime headers match the loaded identity. Existing fake/lifecycle tests cover other failure paths; these two trials do not establish real codec-open/close-fault recovery or browser Stop.

The separate site uses direct Uvicorn HTTPS on192.168.1.83:8444, existing lan.pem/lan-key.pem and explicit private-address binding. Certificate SAN covers the address; CA/hostname verification stays enabled. Ten real TLS checks cover index/health, invalid Host400/cross-origin403/same-origin200, absent session/RTC/OpenAPI/source/key404. All five served build artifacts match local bytes. Original web/dist's five hashes remain unchanged across separate builds. The page imports no LiveKit, microphone or session client; the factory creates no conversation/store/STT/LLM runtime. Pure-ASGI and existing LAN tests cover extraction compatibility. Ctrl-C stops the preview process with exit130 and releases8444; subsequent restart succeeds without restarting either inference service.

The first CLI TLS report v1 proved cache/cancellation but did not independently compare preview response fingerprints. Independent T-112 review found this measurement gap. It is retained as historical, not used alone to attribute candidate performance. The verifier now captures a ready fingerprint, requires it on the cancelled PCM, completed PCM and cached WAV responses, and matches subsequent/final sidecar health. Missing/mismatched headers and changed runtime fail tests. Schema2 records the binding.

Only the three candidate cache WAVs generated here were resolved and PCM-verified, then moved while the candidate site was stopped to .artifacts/breeze-performance/mlx-experimental-lan-v1-cache. They remain recoverable; no unrelated/Quality cache was removed. The corrected uncached v2 CLI run regenerates all three exact PCM hashes, proves first PCM while inference is busy, disconnect cleanup/no partial cache, immediate retry and exact completed legacy WAVs. Every response matches f0cac89f…:

| Preview | First PCM | Complete response | Output duration |
|---|---:|---:|---:|
| warm-companion |0.284105s|3.029754s|4.00s|
| bright-guide |0.296977s|2.861957s|3.76s|
| grounded-mentor |0.293600s|3.359209s|4.48s|

This page still requires the complete response before scheduling playback, so these uncached examples already exceed the2-second playback target. No browser scheduling, actual sound, listening or underrun acceptance was measured. Cached replay is not an uncached latency result. T-014 must test a recipe-bound bounded reserve/credit policy and explicit late-failure behavior without weakening Quality's complete-clip policy.

## Reproduction and source

[LAN operations](../../../operations/lan-voice-site.md#isolated-experimental-mlx-previews) records exact startup/build commands. Set SIMO_BREEZE_ENDPOINT to http://127.0.0.1:7861/v1/audio/speech, UV_CACHE_DIR=/private/tmp/simo-uv-cache and TIKTOKEN_CACHE_DIR=.cache/tiktoken. Run `uv run --frozen simo breeze benchmark --warmups 1 --limit 1 --seeds 17,29 --audio-dir NEW_DIRECTORY --json`, then a separate no-warmup seed17 repeat with a different output directory. Audio writes refuse overwrite. Corrected TLS proof:

```sh
uv run --frozen simo breeze verify-preview --url https://192.168.1.83:8444 \
  --ca-file '/Users/mike/Library/Application Support/mkcert/rootCA.pem' --json
```

Use a genuinely uncached candidate for the cancellation trial. Never delete unrelated caches or fabricate a runtime fingerprint. Boundary/lifecycle probes use stdlib HTTP clients, real loopback sockets, explicit socket shutdown and JSON evidence; no computer-use automation.

Parent base2ffe040/fork a294fe4 plus preserved dirty source, no commits/pushes. Held fork executable digest450b21d39d3682675b03631940f07b86d2079e1e11d118a8e78324bd76cd1056. Launcher SHAc92dca104aa02316276693f894af6e4fd8c81a0762ce8bd79acd85826129ec1f; preview_site SHA5442924ecb97933847d820545cd527b7b50cfb8835eba9030e6a5995ed350a2a; lan_site SHAa787c00f4fc99369b2459bb4e05c6a28889a4c83f9fa54cbfd41c5a03dcb851e; CLI SHA9b14f8d6752fd79ddb9a9c3b516918e50c0c4863a04ca2c85552338253f4e58c; corrected breeze verifier SHA68a965d32c436abc3e72202b9929b997fad2813cb5b9996b36c9fd4976420e8f.

Final171 fork overlay tests,83 locked/three optional skips,135 Simo Python,5 knowledge and25 web tests pass; TypeScript/separate Vite/native build, full parent static and focused fork lint/format pass. [Verification](../verification.md) distinguishes current and earlier gates. [R-112](../results/R-112.md)/[R-113](../results/R-113.md) separate independent CPU/source/artifact review from root's real model/TLS execution. A scoped ty middleware-factory suppression documents Starlette's factory/ASGI alias typing mismatch; BasedPyright and actual ASGI tests cover that boundary. Initial YAML-colon/type/format errors and a missing tokenizer-cache environment were corrected/rerun, not counted as passing attempts.

Local .artifacts/breeze-performance report SHA256:

- mlx-experimental-http-health-v1.json:258e86d957ce0d5783e4a55150c599805bb18b1fc22a824a68c1120a2e9065bf.
- mlx-experimental-http-boundary-v1.json:bc0f20d6c08e0234f68acb4973871bcc9ac8ca2b834101505b6e4a014d852778.
- mlx-experimental-http-seeds-v1.json:8bfd323e54d85395e5e089e96fa1f6ce580c0e97456024db22d8ab0736b29b0c.
- mlx-experimental-http-repeat-v1.json:657c781a4dd560d354c924cb06b24681b0f00ce0fa4664fd0a2c2bbc46b845f3.
- mlx-experimental-http-lifecycle-v1.json:aa5abaf1bb94185c2318ab3de2d32c736e0ca26a7856051c782322003121097f.
- mlx-experimental-site-boundary-v1.json:68b8e0c6ce66a270463f47c47621915da1b076ce6933bc130eab4ce54d7afaeb.
- mlx-experimental-lan-proof-v1.json:82feef81921ee631b65799d3634f6ab80fb1c6fd35b5e0ef53a9a12770c977e9; superseded identity attribution.
- mlx-experimental-lan-proof-v2.json:392f314658628ac56ea2afe6a0408b35d5dd8025f3492c6294497916c77549cc.
- mlx-experimental-final-services-v1.json:9460ed70de95fbc12e419e633ed3ca9e9129612d4dd74df0fe7dde3d6352ed0c; unchanged Quality fingerprint/ready/nonbusy, all five original served assets equal local web/dist, candidate/preview samef0cac89f… and all three completed caches. Quality46660/7860, original HTTPS47503/8443, candidate98272/7861 and preview16500/8444 listeners remain live.

No release/listening/physical-playback/CUDA claim. Model scope remains authorized by D-012; A-006/A-007 and the autonomous goal stay open.
