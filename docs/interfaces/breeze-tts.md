---
type: Interface Contract
title: Breeze-TTS-2 boundary
description: Defines Simo's pinned loopback Breeze-TTS-2 service, PCM contract, Apple Silicon compatibility layer, capacity, and licensing boundary.
tags: [interface, breeze, tts, audio, mps, licensing]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-09-02T14:25:21Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-09-02T14:24:29Z }
stale_after: 2026-12-01
sources:
  - id: breeze-model
    resource: https://huggingface.co/BreezeBlue/Breeze-TTS-2
    title: Breeze-TTS-2 model card
  - id: breeze-upstream
    resource: https://github.com/breezeblue-ai/breeze-tts
    title: Breeze-TTS-2 reference source
  - id: breeze-mps-fork
    resource: https://github.com/mgwilt/breeze-tts-mps/commit/a38d7d1b232dce058cc4e0bf78dc4aa3e0aca2ab
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
simo:
  profile_version: 1
  stable_id: DOC-0008
  authority: interface
  repository_paths: [.gitmodules, vendor/breeze-tts, services/breeze, python/simo/breeze.py, python/simo/inference.py, python/simo/config.py, python/simo/livekit_runtime.py, scripts/setup_models.py, tests/python]
  owner: codex/gpt-5.6-sol
---
# Breeze-TTS-2 boundary

## Pinned deployment

Simo pins the owned `mgwilt/breeze-tts-mps` fork at `a38d7d1b232dce058cc4e0bf78dc4aa3e0aca2ab`, based on official upstream revision `0072588a517f54a3a91d8f566be91cce74b64d13`, and pins `BreezeBlue/Breeze-TTS-2` at `799624c0b4a1daa8db6d28bbd9850043c0270734`. Model download remains opt-in. The model is approximately 7.7 GB and the official deployment target is Linux/CUDA; the fork's Apple Silicon support is a Simo-owned compatibility boundary, not an upstream claim.[^breeze-model][^breeze-upstream][^breeze-mps-fork]

`services/breeze` owns a separate locked Python environment because its PyTorch/Qwen-TTS dependency stack is intentionally isolated from Simo's MLX runtime. It binds only to `127.0.0.1:7860`. The fork selects MPS when CUDA is unavailable, applies eager attention to the nested text encoder, and uses the model's official eager `generate(..., output_audio=True)` path behind the existing HTTP contract on non-CUDA devices. `services/breeze/serve.py` is a thin loopback launcher and Simo-specific health boundary.[^breeze-mps-fork][^simo-breeze-service]

## Request and response

Default endpoint: `http://127.0.0.1:7860/v1/audio/speech`

The client sends `multipart/form-data` fields `text`, `instruction`, `cfg_scale`, and `seed`. Text and instruction must be non-empty; CFG scale must be positive. The first implementation does not expose reference-audio cloning through Simo.

Successful responses are raw mono 16-bit little-endian PCM. `X-Sample-Rate` must be `24000` and `X-Sample-Format` must be `s16le`; incomplete samples, mismatched metadata, non-200 responses, timeouts, and queue overflow fail the current utterance. The LiveKit adapter yields bounded PCM frames and observes cancellation between received chunks.[^simo-breeze-client]

The service accepts only one inference request at a time. A concurrent request returns 409. Health exposes only readiness, busy state, device, dtype, sample rate, and pinned revisions; it does not expose prompts, audio, tokens, paths, or credentials.

## Runtime profiles and rollback

New aliases use `simo.runtime-profile.v2` with Breeze backend, model/revision, voice-design text, instruction, CFG scale, and seed. Profile versions are immutable. Legacy v1 profiles continue to resolve to the pinned Qwen MLX-Audio model and voice. `SIMO_TTS_BACKEND=qwen` explicitly overrides the active profile's TTS selection for an operator rollback in the new process without mutating stored history.

## Performance and rights boundary

On the declared M3 Ultra, eager MPS synthesis produced valid 24 kHz audio but measured p95 first audio of 71.873 seconds and p95 RTF of 13.511. It fails Simo's preview limits of 2 seconds and 1.5 respectively. The current MPS route is therefore functional evaluation infrastructure, not realtime TTS.

The source repository is Apache-2.0, but the distributed model has its own license restricting use to personal, academic, research, education, and other non-commercial purposes. Simo's integration does not broaden those rights; operators must review the model license before use.[^breeze-license]

[^breeze-model]: Breeze-TTS-2 model card, verified 2026-09-02 for model identity, size, audio contract, and official hardware guidance.
[^breeze-upstream]: Official Breeze-TTS-2 source at base revision `0072588a517f54a3a91d8f566be91cce74b64d13`, verified 2026-09-02.
[^breeze-mps-fork]: Simo-owned Breeze MPS fork revision `a38d7d1b232dce058cc4e0bf78dc4aa3e0aca2ab`, verified 2026-09-02 with 31 fork tests and one uncached 23,040-byte PCM response on MPS.
[^breeze-license]: Breeze-TTS-2 model license, verified 2026-09-02; this documentation is not legal advice.
[^simo-breeze-service]: `services/breeze/serve.py` and its isolated lockfile; observed fork-native MPS load and synthesis are recorded in `W-20260802-conversational-identities#E-007`.
[^simo-breeze-client]: `python/simo/inference.py`, `python/simo/livekit_runtime.py`, and focused tests in the implementation based on `f5a039f`.
