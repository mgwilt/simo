---
type: Work Decision Log
title: Finish Simo decisions
description: Records locked product boundaries and evidence-gated runtime choices.
tags: [work, decisions, product, inference]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T02:53:48Z }
sources:
  - id: mlx-audio
    resource: https://github.com/Blaizzy/mlx-audio
    title: MLX-Audio repository
  - id: qwen-tts-mlx
    resource: https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-6bit
    title: Qwen3-TTS 0.6B CustomVoice 6-bit MLX model card
  - id: parakeet-mlx
    resource: https://github.com/senstella/parakeet-mlx
    title: Parakeet MLX repository
  - id: parakeet-model
    resource: https://huggingface.co/mlx-community/parakeet-tdt-0.6b-v3
    title: Parakeet TDT 0.6B v3 MLX model card
  - id: mlx-lm
    resource: https://github.com/ml-explore/mlx-lm
    title: MLX-LM repository
  - id: qwen-text-mlx
    resource: https://huggingface.co/mlx-community/Qwen3.5-4B-4bit
    title: Qwen3.5 4B 4-bit MLX model card
  - id: gemma-terms
    resource: https://ai.google.dev/gemma/terms
    title: Gemma terms of use
  - id: pipecat-silero
    resource: https://docs.pipecat.ai/server/services/vad/silero
    title: Pipecat Silero VAD documentation
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-DECISIONS
  authority: coordination
  repository_paths: [python/simo, include/simo, src, docs]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# Decisions

## D-001: Preserve the three-plane architecture

Pipecat remains the latency-sensitive media/frame plane, Flecs the live semantic state plane, and OKF durable reviewable knowledge. Adapters cross boundaries through bounded value contracts.

## D-002: Finish requires headless and live proof

Deterministic headless acceptance is required for repeatability. A separate live conversation is required for user-visible completion; neither substitutes for the other.

## D-003: Inference choices are replaceable, Mac-native, and evidence-gated

Gemma-family text inference and candidate open-source speech runtimes remain candidates until `T-001` checks current licenses, Apple Silicon/Metal fit, streaming behavior, Pipecat compatibility, and executable serving paths. Core contracts must not encode one model's tokenizer or transport.

## D-004: macOS is the hard target; Gepard is replaceable

The existing Gepard batch adapter remains useful reference code, but its published open-source inference path requires CUDA. Product completion uses the strongest suitable open-source TTS that actually runs locally on the declared Mac and has a truthful streaming/interruption boundary. Gepard may remain optional rather than production-selected.

## D-005: Runtime knowledge is a projection

The Flecs knowledge graph is a refreshable projection of validated OKF concepts. It preserves stable documentation IDs and provenance as component data but uses independent runtime entity IDs and cannot grant authorization or attest execution.

## D-006: Select an MLX-native default inference stack

The macOS default is Qwen3-TTS 0.6B CustomVoice 6-bit through MLX-Audio for speech output, Parakeet TDT 0.6B v3 through Parakeet MLX for speech recognition, and Qwen3.5 4B 4-bit through MLX-LM for text inference.[^mlx-audio][^qwen-tts-mlx][^parakeet-mlx][^parakeet-model][^mlx-lm][^qwen-text-mlx] These are replaceable defaults, not types embedded in the Pipecat/Flecs core contracts. Their model weights remain absent until the large-download checkpoint is explicitly authorized.

Gemma is no longer the default. Older Gemma releases carry separate terms, while the selected Qwen text model has a direct current MLX conversion and an Apache-2.0 upstream lineage.[^gemma-terms][^qwen-text-mlx] A future Gemma adapter remains possible behind the same text-inference contract.

## D-007: Use a built-in synthetic voice by default

The default live proof uses one of the selected TTS model's built-in voices, not voice cloning or reference audio.[^qwen-tts-mlx] This keeps the first product proof reproducible and avoids introducing a real-person consent boundary.

## D-008: Observers cannot advance the semantic world

Pipecat observers may run ahead of ordered frame processing. They therefore enqueue immutable transcript values into a bounded keyed mailbox; only the semantic turn processor can promote the matching current turn into Flecs and advance the world. This preserves observer extensibility without allowing a future transcript to contaminate an earlier inference context.

## D-009: Operational events exclude content by construction

Simo emits fixed-schema aggregate lifecycle, queue, error-count, and timing events. The event API does not accept transcript, prompt, response, audio, model-output, or exception-message fields. User-requested command results remain a separate output channel and may contain explicitly supplied synthetic content.

## D-010: Start local turn detection with a replaceable bounded energy gate (superseded)

The first macOS live path used deterministic normalized-RMS start/stop detection with typed thresholds, pre-roll, and a maximum utterance duration. Human live testing found the gate unstable on the target headset. `D-012` replaces the runtime detector while retaining this aggregate RMS path only as an application-controlled diagnostic.

## D-011: Model installation is explicit, immutable, and fail-closed

The selected repositories are pinned to full revisions and model setup prints a size and disk-space plan without downloading by default. A separate `--accept-download` flag authorizes the transfer. Doctor accepts a local model only after its required files exist and an atomic completion marker matches both the configured repository and revision. A partially downloaded, substituted, or subsequently reconfigured model therefore cannot make live preflight ready.

## D-012: Ratchet strict type safety from an explicit baseline

BasedPyright strict mode covers first-party runtime, tests, and scripts and keeps `reportAny` and `reportExplicitAny` at error severity. The initial 470 diagnostics are recorded in a relative-path baseline instead of being hidden through weaker global settings. New or moved violations fail immediately; baseline reduction remains reviewable follow-up work. Ruff and `ty` remain independent, baseline-free gates so the baseline cannot suppress lint, formatting, or the second checker.

## D-013: Use conditioned Silero with unattended echo acceptance

Runtime turn boundaries use Pipecat's bundled Silero ONNX analyzer with bounded pre-roll, maximum utterance duration, interruption frames, and aggregate confidence telemetry.[^pipecat-silero] Each analysis window receives DC removal and bounded automatic gain derived from application-controlled ambient/speech measurement. RMS calibration remains a privacy-safe optional input diagnostic, not runtime VAD.

Pipecat TTS start/stop contexts and actual PCM duration reserve a half-duplex suppression window so output cannot become a new input turn. Acceptance is unattended: generated speech must form three real Silero utterances and interruption signals, and replaying the same PCM as simulated speaker echo must form none. This proves detector and suppression logic, not subjective headset or room quality.

## D-014: Bound voice responses and select streaming interval by measurement

The realtime path caps generated text at `48` tokens even though the reusable processor default remains `256`. MLX-Audio documents `streaming_interval` as a latency/overhead control; isolated measurement of the pinned Qwen model selected `0.24` seconds as the balanced default. `0.16` emitted sooner but increased total synthesis overhead, while `0.32` had the slowest first chunk.[^mlx-audio]

[^mlx-audio]: MLX-Audio repository and examples, checked 2026-08-02: Apple Silicon speech generation and streaming interfaces.
[^qwen-tts-mlx]: Qwen3-TTS 0.6B CustomVoice 6-bit MLX model card, checked 2026-08-02: MLX-Audio conversion, model size, license metadata, and built-in voices.
[^parakeet-mlx]: Parakeet MLX repository, checked 2026-08-02: Apple Silicon transcription and streaming API.
[^parakeet-model]: Parakeet TDT 0.6B v3 MLX model card, checked 2026-08-02: MLX conversion, size, language coverage, and license metadata.
[^mlx-lm]: MLX-LM repository, checked 2026-08-02: Apple Silicon text-generation runtime and streaming API.
[^qwen-text-mlx]: Qwen3.5 4B 4-bit MLX model card, checked 2026-08-02: current MLX conversion and upstream Apache-2.0 lineage.
[^gemma-terms]: Gemma terms of use, checked 2026-08-02: separate use and distribution terms for covered Gemma releases.
[^pipecat-silero]: Pipecat Silero VAD documentation, checked 2026-08-02: local ONNX voice confidence analysis and configurable temporal thresholds.
