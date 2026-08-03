---
type: Work Evidence
title: Synthetic Silero and playback echo
description: Records the unattended real-model proof for conditioned Silero detection and playback-echo suppression.
tags: [work, evidence, silero, vad, audio, macos]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T03:30:00Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-E-012
  authority: evidence
  repository_paths: [python/simo, tests/python, README.md]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent, evidence_id: E-012 }
---
# Synthetic Silero and playback echo

## Claim

Simo can validate its real conditioned Silero detector and half-duplex playback suppression without a microphone, speaker, human timing, or retained real-person audio. This evidence does not attest subjective headset or room quality.

## Method

The application generated `The blue door is open.` with the pinned Qwen3-TTS MLX model, resampled the signed 16-bit mono PCM from 24 kHz to 16 kHz, surrounded it with deterministic silence, and fed 20 ms frames through the same `ObservedSileroVADAnalyzer` and `SileroUtteranceProcessor` used by live mode. It then replayed the same speech frames while the shared TTS playback context and duration reservation were active.

The proof retained only the existing ignored synthetic WAV artifact and aggregate results. It did not open CoreAudio devices.

## Result

Command: `UV_CACHE_DIR=/private/tmp/simo-uv-cache uv run --extra inference simo prove-models`

- Synthetic speech duration: `1.680` seconds.
- Silero analysis: `77` windows, mean confidence `0.477570`, maximum confidence `0.990626`.
- Accepted speech utterances: `1`.
- Simulated playback input chunks suppressed: `84/84`.
- Additional turns caused by simulated playback echo: `0`.
- Parakeet transcript: exact expected synthetic phrase.
- Real semantic pipeline: one context injection, world revision `1`, zero observer mailbox drops.
- Model timings: warm STT `486.79` ms; warm text `477.72` ms; warm TTS first chunk `1074.72` ms and total `5617.53` ms.

Repository verification also passed `65` Python tests, native build/tests, Ruff lint/format, `ty`, baseline-ratcheted BasedPyright strict, documentation validation, knowledge regression, and whitespace validation.

## Limits

This proves executable detector and echo-gating behavior against generated speech on the declared Apple Silicon host. It does not prove acoustic echo cancellation, barge-in while half-duplex suppression is active, subjective voice quality, or performance for every physical microphone and room.
