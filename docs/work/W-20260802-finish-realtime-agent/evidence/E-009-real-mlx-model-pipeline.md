---
type: Evidence Record
title: Real MLX model pipeline evidence
description: Records immutable model execution, cold and warm timings, synthetic speech round trip, Pipecat/Flecs integration, and PortAudio speaker output on the declared Mac.
tags: [evidence, macos, mlx, pipecat, flecs, stt, text, tts, audio]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T02:08:49Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T02:08:49Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-E-009
  authority: evidence
  repository_paths: [README.md, python/simo/cli.py, python/simo/inference.py, python/simo/model_proof.py, python/simo/adapters/pipecat, tests/python/test_inference.py, tests/python/test_model_proof.py]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# E-009: Real MLX model pipeline

- Revision: `ad496532238add16d357e4d07f2d48dd1792d7b5` with the chat-template correction at `1760104` and model-proof entrypoint at `1ce3928`.
- Environment: Mac Studio, Apple M3 Ultra, 512 GB unified memory, MLX Metal, default Arctis Nova Pro input/output, and the three model IDs and full revisions recorded by `E-008`.
- Method: ran live doctor outside the sandbox; executed `simo prove-models`; required Qwen text to return the exact bounded response `SIMO TEXT READY`; synthesized the synthetic phrase “The blue door is open.” with built-in voice Aiden; resampled only that generated PCM to 16 kHz and required Parakeet to reproduce the phrase exactly; then reused the loaded providers in a real Pipecat worker that performed STT, one Flecs context injection, bounded Qwen generation, and Qwen TTS. Finally wrote the ignored synthetic 24 kHz WAV once through default PortAudio output. No cloned or real-person voice was used.
- Result: text completed in 2740 ms cold and 200 ms warm. TTS produced 1.68 seconds/80,640 bytes of PCM with first chunk at 868 ms cold and 97 ms warm. STT completed in 727 ms cold and 97 ms warm, a 0.058 warm realtime factor, with exact transcript. The integrated turn produced one context injection at world revision 1, projected 32 OKF concepts and 3 links, emitted one text frame and 10 audio frames/138,240 bytes, and recorded zero model errors or mailbox drops. PortAudio wrote the proof WAV in 1.94 seconds.
- Live attempt boundary: a separate 108-second `simo live` session became ready and shut down cleanly with zero errors or drops, but detected no utterance. A three-second no-storage level diagnostic reported aggregate peak RMS `0.012764`, below the configured `0.02` speech-start threshold.

Proves: immutable local weights load and execute through Simo's adapters on MLX Metal; Qwen chat templating suppresses the reasoning preamble; generated speech has valid PCM and round-trips through Parakeet; real STT, Flecs/OKF context, text generation, and TTS compose through Pipecat; default PortAudio output accepts the generated audio.

Does not prove: human microphone speech, subjective voice quality, three human turns, barge-in, cancellation during an active Metal kernel, acoustic robustness, or a latency distribution beyond this one synthetic run. The no-utterance session is not evidence for `A-008`.
