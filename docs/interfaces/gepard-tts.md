---
type: Interface Contract
title: Gepard TTS boundary
description: Defines Simo's implemented HTTP and audio contract for the open-source Gepard reference server and Pipecat.
tags: [interface, audio, tts, gepard, pipecat]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:53:21Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:53:21Z }
stale_after: 2026-09-02
sources:
  - id: gepard-model
    resource: https://huggingface.co/nineninesix/gepard-1.0
    title: Gepard 1.0 model card
  - id: gepard-reference
    resource: https://github.com/nineninesix-ai/gepard-inference
    title: Gepard reference inference server
  - id: gepard-adapter
    resource: ../../python/simo/adapters/pipecat/gepard_tts.py
    title: Simo Pipecat Gepard TTS adapter
  - id: gepard-tests
    resource: ../../tests/python/test_pipecat_adapters.py
    title: Simo Pipecat adapter tests
simo:
  profile_version: 1
  stable_id: DOC-0003
  authority: interface
  repository_paths: [python/simo/gepard.py, python/simo/adapters/pipecat/gepard_tts.py, tests/python]
  owner: unassigned
---
# Gepard TTS boundary

## Upstream deployment boundary

Gepard 1.0 is an approximately 0.6B-parameter autoregressive TTS model using a 22,050 Hz NanoCodec audio representation. Its published realtime measurements are for the vLLM path on CUDA GPUs, while the reference PyTorch runner is not optimized for throughput.[^gepard-model]

The open-source reference inference repository requires Python 3.12 and a CUDA GPU. Its documented basic interface loads the model in a separate server and accepts `POST /synthesize` JSON with `text`, returning a WAV response; optional reference audio and CFG controls are supported by the reference tooling.[^gepard-reference]

Simo does not embed, download, or initialize the model. The Gepard process is an external local service with its own GPU, model, codec-license, capacity, and consent responsibilities.

## Implemented request

Default URL: `http://127.0.0.1:8000/synthesize`

```json
{
  "text": "required non-empty text",
  "reference": "optional reference path",
  "cfg_scale": 3.0
}
```

`reference` and `cfg_scale` are omitted when unset. The framework-neutral `GepardHttpClient` provides the synchronous reference boundary. `GepardTTSService` uses an asynchronous Pipecat-owned HTTP session, supports a caller-provided session, and turns non-200 responses or bounded transport/codec failures into `ErrorFrame` values.[^gepard-adapter]

## Implemented response

Simo currently accepts only mono, 16-bit PCM WAV at 22,050 Hz. It strips the WAV container and emits complete sample frames in deterministic 20 ms chunks by default. Each Pipecat `TTSAudioRawFrame` preserves the caller's context ID.[^gepard-adapter]

Tests demonstrate the endpoint and payload, WAV validation, deterministic PCM chunk reconstruction, Pipecat frame generation, context propagation, and bounded HTTP-error output without a live server.[^gepard-tests]

## Latency boundary

The reference `/synthesize` adapter reads the complete WAV before yielding Pipecat audio. It is therefore a correct integration baseline, not a streaming or realtime proof. Achieving Gepard's published low time-to-first-audio requires a streaming vLLM serving path and a corresponding interruptible Pipecat service contract; neither is implemented here.[^gepard-model][^gepard-reference]

No current evidence proves model startup, CUDA compatibility, speech correctness, voice similarity, consent enforcement, audio quality, interruption behavior against a live server, concurrency, or end-to-end latency.

[^gepard-model]: Gepard 1.0 model card, checked 2026-08-02: model details, highlights, and deployment caveats.
[^gepard-reference]: Gepard reference inference README, checked 2026-08-02: installation and `/synthesize` quick-start contract.
[^gepard-adapter]: `python/simo/gepard.py` and `python/simo/adapters/pipecat/gepard_tts.py` at revision `37ff732690081dff4ef3c02487d9adb6cf9287b2`.
[^gepard-tests]: `tests/python/test_gepard.py` and `tests/python/test_pipecat_adapters.py` at revision `37ff732690081dff4ef3c02487d9adb6cf9287b2`.
