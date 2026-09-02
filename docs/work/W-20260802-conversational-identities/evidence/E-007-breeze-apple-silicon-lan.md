---
type: Evidence Record
title: Breeze Apple Silicon and LAN site evidence
description: Records pinned Breeze-TTS-2 execution and benchmark results on the M3 Ultra plus trusted-CA host routing and curated voice previews.
tags: [evidence, breeze, tts, mps, livekit, lan, https]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-09-02T14:25:21Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-09-02T14:24:29Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-E-007
  authority: evidence
  repository_paths: [.gitmodules, vendor/breeze-tts, services/breeze, python/simo/breeze.py, python/simo/inference.py, python/simo/livekit_runtime.py, python/simo/lan_site.py, python/simo/config.py, python/simo/persistence.py, python/simo/cli.py, scripts/setup_models.py, scripts/setup_lan_tls.py, web, tests/python]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# E-007: Breeze Apple Silicon and LAN site

- Source state: Simo implementation commit `c037f5f`; owned `mgwilt/breeze-tts-mps` fork commit `a38d7d1b232dce058cc4e0bf78dc4aa3e0aca2ab`, based on official upstream `0072588a517f54a3a91d8f566be91cce74b64d13`; model pinned at `799624c0b4a1daa8db6d28bbd9850043c0270734`.
- Environment: Mac Studio, Apple M3 Ultra, 512 GB unified memory, macOS 26.5, Python 3.13.12 sidecar, PyTorch 2.9.1, bfloat16 MPS, LiveKit Server 1.13.5, Caddy 2.11.4, and mkcert 1.4.4.
- Integration method: Simo pins its owned fork as `vendor/breeze-tts` and runs it in an isolated service environment bound to `127.0.0.1:7860`. The fork selects MPS, applies eager attention to the nested text encoder, and uses the model's official eager generation path because upstream's streaming runtime is CUDA-only. The thin Simo launcher supplies loopback and health policy. The in-process LiveKit TTS adapter consumes bounded 16-bit PCM and supports cancellation between returned chunks.
- Health result: `simo breeze doctor` returned ready, not busy, MPS, bfloat16, 24,000 Hz, and exact source/model revisions. The live runtime doctor also passed native core, Parakeet, MLX-LM, LiveKit, Silero, Metal, local devices, all model markers, and the Breeze service.
- Benchmark method: `simo breeze benchmark --json` ran three warmups followed by ten fixed English prompts with instruction CFG scale 4.0 and seed 42. First audio is necessarily equal to nearly complete generation latency because eager MPS does not provide upstream CUDA streaming.
- Benchmark result: p50/p95 first audio 51.243/71.873 seconds; p50/p95 RTF 13.163/13.511; sample audio durations 3.04–5.36 seconds; all ten responses returned non-empty 24 kHz PCM. The preview limits of p95 first audio at most 2 seconds and p95 RTF at most 1.5 both failed.
- Fork-native result: 31 fork tests passed. The real fork-backed service loaded the pinned model on MPS with bfloat16, reported 24,000 Hz, and an uncached `Hello.` request returned HTTP 200 with `X-Sample-Rate: 24000`, `X-Sample-Format: s16le`, and 23,040 PCM bytes.
- LAN method: an isolated test alias was served through Caddy at `https://mikesMacStudio.local:8443` and `https://192.168.1.84:8443`. Caddy terminated the generated certificate, proxied only `/api/*` and `/rtc*`, and served the built Vite site; LiveKit advertised TCP 7881 and UDP 7882 while the model and internal services stayed loopback-only.
- LAN result: using the generated CA explicitly, HTTPS health returned ready and the static document returned `Simo Voice`. Initial operator testing found that a failed connection consumed the only session token and that access through the IPv4 fallback still returned an mDNS signaling URL. The corrected endpoint permits retries for the same fixed identity, validates the request hostname/IP, and returns a matching WSS address. The mic-free palette exposes three curated voice instructions and caches generated WAV responses under ignored local artifacts. The app reached its ready state and shut down cleanly on operator interrupt. No security interstitial was bypassed.
- Regression at evidence capture: native build; 115 Python tests; Ruff; Ruff format; `ty`; BasedPyright strict; TypeScript; production Vite build; documentation validation; five knowledge regression tests; and diff whitespace passed. All three live curated preview requests returned 200 and the listing reported every WAV cached.

Proves: `A-016`; the exact Breeze source/model execute on the declared Apple Silicon host and produce the required PCM contract; runtime profiles preserve Breeze parameters and Qwen rollback; the benchmark reports the failed performance target honestly; the LAN edge serves certificate-validated HTTPS, keeps retries on one fixed browser identity, follows validated hostname/IP access, and exposes only curated locally cached previews without exposing model endpoints or room secrets.

Does not prove: the preview latency target, incremental MPS streaming, subjective voice quality, long-session stability, concurrent synthesis, iPhone/iPad certificate trust, Safari microphone permission, end-to-end browser WebRTC media, interruption from a physical device, router/firewall compatibility outside the observed host, Internet safety, production deployment, or commercial model rights.
