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

Simo can validate a three-turn real-model voice path, conditioned Silero detector, half-duplex playback suppression, and bounded response settings without a microphone, speaker, human timing, or retained real-person audio. This evidence does not attest subjective headset or room quality.

## Method

The application generated `The blue door is open.` with the pinned Qwen3-TTS MLX model, resampled the signed 16-bit mono PCM from 24 kHz to 16 kHz, surrounded three copies with deterministic silence, and fed 20 ms frames through the same `ObservedSileroVADAnalyzer` and `SileroUtteranceProcessor` used by live mode. It then replayed the same speech frames while the shared TTS playback context and duration reservation were active. Three utterance values traversed real Parakeet STT, Flecs context injection, Qwen text, and Qwen TTS.

The TTS interval was also measured in one warm pinned-model process at `0.32`, `0.24`, and `0.16` seconds using the same response sentence twice per interval. This isolated chunk benchmark avoids model-load noise.

The proof retained only the existing ignored synthetic WAV artifact and aggregate results. It did not open CoreAudio devices.

## Result

Command: `UV_CACHE_DIR=/private/tmp/simo-uv-cache uv run --extra inference simo prove-models`

- Synthetic speech duration: `1.680` seconds per turn.
- Silero analysis: `220` windows, mean confidence `0.510040`, maximum confidence `0.995190`.
- Accepted speech utterances / interruption signals: `3 / 3`.
- Simulated playback input chunks suppressed: `84/84`.
- Additional turns caused by simulated playback echo: `0`.
- Parakeet transcript: exact expected synthetic phrase.
- Real semantic pipeline: three context injections, world revision `3`, `39` TTS audio frames, zero observer mailbox drops.
- Post-change direct model timings: warm STT `394.15` ms; warm text `236.60` ms; warm TTS first chunk `252.31` ms and total `1790.85` ms.
- Streaming interval benchmark: `0.32` first/total `95.21/1054.86` ms; `0.24` `78.72/1119.35` ms; `0.16` `58.71/1207.43` ms. The selected `0.24` interval improves first emission without the larger total overhead of `0.16`.

Repository verification also passed `65` Python tests, native build/tests, Ruff lint/format, `ty`, baseline-ratcheted BasedPyright strict, documentation validation, knowledge regression, and whitespace validation.

## Limits

This proves executable detector and echo-gating behavior against generated speech on the declared Apple Silicon host. It does not prove acoustic echo cancellation, barge-in while half-duplex suppression is active, subjective voice quality, or performance for every physical microphone and room.
