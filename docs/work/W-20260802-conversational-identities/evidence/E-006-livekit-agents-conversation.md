---
type: Evidence Record
title: LiveKit Agents conversation and headset-room evidence
description: Records the observed two-process local-model conversation loop and one-human native headset room startup.
tags: [evidence, livekit, agents, webrtc, models, headset, attribution, privacy]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T16:17:35Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T16:17:35Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-E-006
  authority: evidence
  repository_paths: [python/simo/adapters/livekit, python/simo/livekit_runtime.py, python/simo/livekit_agent_lab.py, python/simo/livekit_local_talk.py, python/simo/livekit_local_server.py, python/simo/cli.py, python/simo/doctor.py, tests/python]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# E-006: LiveKit Agents conversation and headset room

- Source revisions: LiveKit Agents conversation lab `649910167dfebf0458d8d3ba790b63237933b71d`; local headset room `fac700e8141808aa032ccc13c891c6be01af9595`.
- Environment: Mac Studio with Apple M3 Ultra, Python 3.13.7, LiveKit server 1.13.5, LiveKit Agents 1.6.7, LiveKit RTC 1.1.13, local pinned MLX models, Flecs 4.1.5, and Silero from the pinned LiveKit plugin.
- Two-process method: `simo lab converse --turns-per-alias 2 --max-duration-s 180 --json` created separate Ada and Bea stores and personas, started a loopback-only LiveKit server, spawned two OS processes, and allowed interaction only through synthesized room audio. The run enforced remote-identity attribution, distinct process/SID identity, no raw-audio retention, transcript reviewability, no adjacent duplicate turns, and complete generated voice text.
- Two-process result: elapsed 35.190 seconds; distinct PIDs 29512 and 29511; distinct SIDs `PA_FaFJSeXPeWwV` and `PA_GEqtbkJbSDiy`; two local spoken turns per alias; three remote synthetic-audio user turns; zero self-echo turns, unexpected identities, attribution errors, duplicate turns, or incomplete generated turns; one interrupted spoken turn; zero event-bridge drops or failures. Both persisted conversations are reviewable. The local ignored result artifact is `.artifacts/livekit-agents-lab/debug-20260803-c/result.json`.
- Headset method: `simo talk --alias … --max-duration-s 2 --json` used LiveKit `PlatformAudio` with WebRTC echo cancellation, noise suppression, and automatic gain control, selected the system-default Arctis Nova Pro microphone and speaker, joined a human participant and alias participant to a fresh loopback room, then stopped at the bound.
- Headset result: distinct human and alias SIDs, native microphone-source publication, LiveKit-native live preflight ready, zero retained raw audio, and a persisted resumable conversation record. No human speech was required or asserted.
- Regression result: 108 Python tests, Ruff `ALL`, Ruff format, BasedPyright strict, and `ty` passed before `fac700e`; its pre-commit hook also passed documentation and five knowledge regression tests.

Proves: `A-008`; LiveKit Agents owns the actual local-model TTS-to-WebRTC-to-Silero-to-STT-to-Flecs-to-next-response loop in two independent processes; subscription and persistence preserve declared remote identities; primary transcripts are reviewable; raw audio defaults off; the macOS headset command can attach native input/output as an independent human RTC participant.

Does not prove: ten held-out scenarios or three seeds, endpoint or response latency distributions, 95% barge-in recovery, background false-start rate, subjective human naturalness, transcript accuracy across accents/noise, memory learning from a room conversation, autonomous evaluation, candidate promotion, canary rollback, complete Pipecat removal, or production deployment. The one interrupted turn remains a tuning signal rather than a hard-floor pass.
