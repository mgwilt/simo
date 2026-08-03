---
type: Architecture Concept
title: Local macOS voice pipeline
description: Defines Simo's implemented Pipecat local-audio topology, bounded utterance detection, interruption path, and resource lifecycle.
tags: [architecture, macos, voice, pipecat, mlx, audio, interruption]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T01:35:05Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T01:35:05Z }
sources:
  - id: pipecat-local-transport
    resource: ../../vendor/pipecat/src/pipecat/transports/local/audio.py
    title: Pinned Pipecat local audio transport
  - id: live-runtime
    resource: ../../python/simo/runtime.py
    title: Simo live runtime owner
  - id: local-audio-boundary
    resource: ../../python/simo/adapters/pipecat/local_audio.py
    title: Simo local utterance and transport adapter
  - id: live-tests
    resource: ../../tests/python/test_live_runtime.py
    title: Simo live runtime tests
  - id: nltk-data-index
    resource: https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/index.xml
    title: NLTK data package index
simo:
  profile_version: 1
  stable_id: DOC-0005
  authority: architecture
  repository_paths: [pyproject.toml, uv.lock, python/simo/config.py, python/simo/doctor.py, python/simo/runtime.py, python/simo/adapters/pipecat, scripts/setup_live_data.py, tests/python]
  owner: unassigned
---
# Local macOS voice pipeline

## Implemented topology

Simo uses Pipecat's pinned `LocalAudioTransport`, which opens the selected or default PortAudio devices, produces 16-bit PCM microphone frames, and writes output PCM to the speaker. Simo fixes the input contract at 16 kHz mono for Parakeet and the output contract at 24 kHz mono for Qwen3-TTS.[^pipecat-local-transport][^live-runtime]

```text
PortAudio microphone (16 kHz mono PCM)
  -> bounded energy utterance detector + interruption
  -> replaceable Parakeet MLX recognizer
  -> final Pipecat transcription observation
  -> ordered Flecs promotion + immutable context snapshot
  -> replaceable Qwen MLX text generator
  -> streaming Qwen MLX-Audio TTS
  -> PortAudio speaker (24 kHz mono PCM)
```

The Pipecat worker owns frame scheduling and interruption propagation. The Simo live owner retains the native Flecs world, validated OKF projection, observer mailbox, model adapters, transport, worker, and terminal operational metrics for one process-local session.[^live-runtime]

## Utterance and interruption boundary

`EnergyUtteranceProcessor` consumes microphone frames rather than forwarding raw audio. It uses configurable normalized RMS, start/stop durations, pre-roll, and a maximum utterance duration. On speech start it emits `UserStartedSpeakingFrame` and `InterruptionFrame`; Pipecat can then cancel current inference/TTS work and flush interruptible speaker output. On speech stop it emits one bounded `PCMUtteranceFrame` for local recognition.[^local-audio-boundary]

This energy detector is deterministic, small, and replaceable. It is not speaker identification, semantic turn detection, echo cancellation, or a claim of robust performance in noise. Headphones are the current operational recommendation because speaker audio can re-enter the microphone.

## Device and data preflight

Live preflight checks Apple Silicon, the native core, all MLX modules, PyAudio, an available MLX Metal device, selected/default input and output devices with compatible channels, the NLTK sentence tokenizer, and all three model directories. Device indices and utterance thresholds are typed environment configuration. The small tokenizer installer verifies NLTK's published SHA-256, download and unpacked-size bounds, archive paths, and expected English data before writing ignored cache storage.[^nltk-data-index]

## Lifecycle

The live command builds the complete pipeline only after preflight succeeds. Pipecat worker setup/teardown owns processors; Simo additionally closes input/output streams, shuts down the PortAudio output executor, terminates PyAudio, closes the native world, and emits terminal privacy-safe metrics. Normal and task-cancelled no-weight tests exercise those ownership paths.[^live-tests]

## Evidence boundary

Implementation revision `7f390b1325c48f7161294ef5a001b523e7b9428f` passes the native build, 47 Python tests, documentation and knowledge validation, changed-file Ruff lint/format checks, and whitespace validation. Outside the sandbox on the declared M3 Ultra, live preflight proves MLX Metal, PyAudio, default Arctis Nova Pro input/output, and the checksum-pinned tokenizer are available. The only failed preflight checks are the three intentionally absent model directories.

This proves pipeline construction, real Pipecat worker setup/teardown with fake inference, frame ordering, bounded utterance behavior, interruption-frame emission, configured device selection, PortAudio resource release, and truthful device/runtime preflight. It does not prove microphone capture, model execution, transcription quality, generated speech, audible playback, acoustic behavior, measured realtime latency, or human barge-in.

[^pipecat-local-transport]: `vendor/pipecat/src/pipecat/transports/local/audio.py` and `vendor/pipecat/pyproject.toml` at pinned Pipecat revision `b114a367a32166207712e8a9c352215a6e24a0db`.
[^live-runtime]: `python/simo/runtime.py`, `python/simo/doctor.py`, and `python/simo/config.py` at revision `7f390b1325c48f7161294ef5a001b523e7b9428f`.
[^local-audio-boundary]: `python/simo/adapters/pipecat/local_audio.py` at revision `7f390b1325c48f7161294ef5a001b523e7b9428f`.
[^live-tests]: `tests/python/test_live_runtime.py`, `tests/python/test_local_audio.py`, `tests/python/test_doctor.py`, and `tests/python/test_setup_live_data.py` at revision `7f390b1325c48f7161294ef5a001b523e7b9428f`.
[^nltk-data-index]: NLTK data package index, checked 2026-08-02: `punkt_tab` archive URL, SHA-256, compressed size, and uncompressed size.
