---
type: Evidence Record
title: Bidirectional two-process WebRTC audio evidence
description: Records the observed self-hosted LiveKit room, audio-only subscription, participant attribution, and no-self-echo transport proof.
tags: [evidence, livekit, webrtc, pipecat, audio, attribution, privacy]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T05:28:47Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T05:28:47Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-E-005
  authority: evidence
  repository_paths: [pyproject.toml, uv.lock, python/simo/adapters/pipecat/livekit_audio.py, python/simo/adapters/pipecat/local_audio.py, python/simo/livekit_probe.py, python/simo/cli.py, tests/python/test_livekit_audio.py, tests/python/test_livekit_probe.py, tests/python/test_local_audio.py]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-conversational-identities }
---
# E-005: Bidirectional two-process WebRTC audio

- Source revisions: `00033bd5ab3e35c325f8fe06f84878b58906fe89` and `5cc44b908c6885f759f3e9ea8dbfd0e6785fcf59`.
- Environment: macOS Apple Silicon, LiveKit server 1.13.5 from the Homebrew `livekit` formula, LiveKit Python SDK 1.1.14, LiveKit API 1.2.0, Pipecat 1.7.1.dev14, and the frozen Simo environment.
- Security and subscription method: each child received a room-scoped identity token through environment-held development credentials. Tokens could join, publish microphone-source audio, and subscribe, but could not publish data. The first-party Pipecat transport connected with automatic subscription disabled and subscribed only to audio from one explicitly allow-listed remote identity. Unencrypted signaling was accepted only on loopback.
- Synthetic method: `simo lab prove-webrtc --json` started a loopback-only self-hosted server, spawned independent initiator and responder processes, generated voiced PCM in memory, published one signal from each process, required the responder to observe the initiator before replying, and terminated both workers and the server under fixed timeouts. It did not open a microphone or speaker and retained no raw audio.
- Observed result: the processes had PIDs 53160 and 53159 and distinct LiveKit SIDs. The initiator observed 28 remote frames and 8,960 samples; the responder observed 32 remote frames and 10,240 samples. Both observed the expected remote identity and SID. Aggregate self-echo frames and unexpected-identity frames were zero. The room and identities were randomized per run.
- Regression result: pre-commit passed Ruff `ALL`, format, `ty`, BasedPyright strict, documentation, and knowledge checks. Pre-push rebuilt and tested the native core and passed 91 Python tests, documentation validation, and five knowledge tests.
- Architecture disposition: `D-009` later selected LiveKit Agents as Simo's sole realtime orchestrator. This record remains immutable evidence for the underlying LiveKit room and the former Pipecat boundary, but it is only a migration baseline and must be replaced before Pipecat removal.

Proves: the transport portions of `A-008`; two independent Simo processes can join one self-hosted LiveKit room, publish and receive audio through Pipecat in both directions, subscribe only to the declared remote audio identity, preserve transport participant attribution, reject self-echo, report structured aggregate evidence, and shut down without raw-audio retention.

Does not prove: the complete `A-008` TTS-to-WebRTC-to-VAD-to-STT-to-Flecs loop, intelligible speech synthesis, transcript accuracy, conversation persistence in the room runner, barge-in, interruption recovery, ten held-out scenarios, latency floors, model quality, persona distinctiveness, learning from room conversations, autonomous evaluation, promotion, or rollback.
