---
type: Work Checkpoint
title: Finish Simo checkpoint
description: Captures the current resumable product-completion state.
tags: [work, checkpoint, product]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T02:17:32Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-CHECKPOINT
  authority: coordination
  repository_paths: [docs/work/W-20260802-finish-realtime-agent]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# Checkpoint

- Base revision: `43c5523ef9b935f58a3c9474d7cc8bfa4eb69968`.
- Dirty paths at activation: none.
- Completed predecessor: `W-20260802-semantic-context-spine` (`DOC-0002`, `DOC-0003`).
- Completed: `T-001` selected the MLX-native Qwen3-TTS 0.6B CustomVoice 6-bit, Parakeet TDT 0.6B v3, and Qwen3.5 4B 4-bit defaults for the Apple M3 Ultra target.
- Completed: `T-002` added the installed `simo` command, typed environment configuration, a truthful two-mode preflight, a system-compiler native build, and the deterministic headless lifecycle at `800e5d0`.
- Completed: `T-003` added the causal observer mailbox, ordered Flecs promotion, immutable revisioned context frames, bounded formatting/freshness, deterministic text and PCM TTS providers, and a real Pipecat pipeline at `6ea58b9`.
- Completed: `T-004` added validation-before-mutation, two-pass concept/link loading, typed Flecs `references` pairs, provenance/freshness components, private runtime identities, immutable graph snapshots, and incremental removal at `0a2b290`.
- Completed: `T-005` installed the optional MLX runtime set, verified Metal/API availability outside the sandbox, and added lazy Parakeet streaming-session and MLX-LM text adapters plus Pipecat processors at `754265a`.
- Completed: `T-006` added lazy Qwen3-TTS generation through MLX-Audio, bounded cross-thread streaming, signed 16-bit mono PCM framing, Pipecat contextual audio frames, cooperative cancellation between generated chunks, and bounded error propagation at `f07a5e5`.
- Completed: `T-007` added a pure fixed-schema privacy-safe JSONL stream, aggregate queue/world/stage metrics, inference timing including first generated TTS audio, normal/cancelled lifecycle reporting, cancellation cleanup tests, terminal-interrupt status, and the operator contract at `e5a6f6a`.
- Progress: `T-008` has the installed/locked PyAudio transport, typed device/VAD configuration, bounded utterance and interruption processor, complete local Pipecat pipeline owner, explicit PortAudio cleanup, checksum-pinned small-data setup, fake-inference worker lifecycle proof, immutable model installer, and outside-sandbox device preflight at `7f390b1` and `3be0e37`.
- Completed model gate: after authorization, all three pinned repositories downloaded with matching completion markers and live doctor became ready. Revisions `1760104`, `1ce3928`, and `ad49653` correct Qwen chat templating, add repeatable cold/warm proofs, and execute real Parakeet STT → Flecs context → Qwen text → Qwen TTS through Pipecat. `E-009` verifies `A-006` and `A-007`.
- Live attempts: application-controlled acoustic calibration measured usable RMS separation and recommended `0.01535`. The energy detector then recorded three speech starts, three STT calls, two Flecs context promotions, two text calls, and four TTS calls with zero errors or drops, but the user judged both VAD and response performance unacceptable. One TTS call occupied `6.874` seconds and first generated audio was about `0.906` seconds after TTS began.
- Silero progress: revisions `e4d777d`, `0fea623`, and `ed30e7f` replace runtime RMS gating with Pipecat's bundled Silero ONNX analyzer, preserve bounded utterances/interruption signals, and add content-free input/confidence aggregates. A Python 3.13 one-element-array conversion bug in the diagnostic wrapper was reproduced and fixed with a regression test. The corrected live probe received `2602` PortAudio chunks and evaluated `1626` Silero windows, but the Arctis processed stream peaked at only `0.031398` confidence and produced no turn at the standard `0.5` threshold. Device selection was confirmed as the default one-channel Arctis input. No raw audio or transcripts were retained by these diagnostics.
- Completed quality gate: revision `8b1cb34` locks Ruff 0.12.11 and Pyright 1.1.411, passes the native build, 56 Python tests, first-party runtime type checking with zero findings, repository-wide first-party lint/format, 33-concept documentation validation, five knowledge regression tests, and whitespace validation. `A-004`, `A-009`, and `A-010` are now satisfied.
- Blocker: none.
- Next action: make Silero confidence calibration or microphone input conditioning application-controlled, then constrain/stream the slow response path and rerun the human three-turn context and interruption acceptance. Do not claim `A-008` from detector counters or model calls alone.
