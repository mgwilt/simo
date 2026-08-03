---
type: Work Checkpoint
title: Finish Simo checkpoint
description: Captures the current resumable product-completion state.
tags: [work, checkpoint, product]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T04:09:36Z }
simo:
  profile_version: 1
  stable_id: W-20260802-finish-realtime-agent-CHECKPOINT
  authority: coordination
  repository_paths: [docs/work/W-20260802-finish-realtime-agent]
  owner: codex/gpt-5.6-sol
  work: { parent_id: W-20260802-finish-realtime-agent }
---
# Checkpoint

- Terminal implementation revision: `6907ee559664d1b443dab35c1f9ac65f0f22fa56`.
- Dirty paths at activation: none; closure documentation is the only expected successor diff.
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
- Silero progress: revisions `e4d777d`, `0fea623`, and `ed30e7f` replaced runtime RMS gating with Pipecat's bundled Silero ONNX analyzer, preserved bounded utterances/interruption signals, and added content-free input/confidence aggregates. Application-controlled measurement found that per-window DC removal plus bounded gain separated ambient (`0.075476` maximum) from speech (`0.906290` maximum) on the Arctis stream. Runtime confidence is now `0.10` with `32` ms start and `320` ms stop bounds.
- Completed unattended three-turn gate: `simo prove-models` no longer requires CoreAudio devices. Pinned Qwen speech produced exactly three conditioned Silero utterances and three interruption signals across `220` analyzed windows (`0.995190` maximum confidence); replaying it as speaker echo suppressed all `84` input chunks and produced zero additional turns. The same run reproduced the exact Parakeet transcript, completed three real Pipecat/Flecs context injections, advanced world revision to `3`, emitted `39` TTS audio frames, and reported zero observer-mailbox drops. `E-012` satisfies `A-008` and `A-013` without human timing or participation.
- Completed bounded response tuning: live text output now defaults to `48` tokens instead of the adapter's general `256`; isolated pinned-model measurement selected a `0.24` second TTS interval over `0.32` and `0.16`. The balanced interval reduced first chunk from `95.21` to `78.72` ms with about `6%` total overhead; the post-change full proof recorded direct warm first audio at `252.31` ms. `A-014` is satisfied, while repeated p95 end-to-end latency remains unclaimed.
- Completed quality gate: revision `8b1cb34` locks Ruff 0.12.11 and Pyright 1.1.411, passes the native build, 56 Python tests, first-party runtime type checking with zero findings, repository-wide first-party lint/format, 33-concept documentation validation, five knowledge regression tests, and whitespace validation. `A-004`, `A-009`, and `A-010` are now satisfied.
- Completed strict static gate: on the working tree based at `4672689`, Ruff 0.14.14 selects `ALL` with documented Simo exclusions, `ty` 0.0.14 checks runtime/tests/scripts with warnings as errors, and BasedPyright 1.39.9 applies strict mode plus `reportAny` and `reportExplicitAny` against a checked-in 470-diagnostic baseline. The installed pre-commit launcher invokes Lefthook, and `--all-files` executes every configured pre-commit job; the installed pre-push launcher executes the native build, 61 Python tests, 35-concept documentation validation, and five knowledge tests. Managed `.git` permissions prevented Lefthook from replacing the already-installed launcher files. `A-012` is satisfied by `E-011`.
- Terminal state: all acceptance and execution items are complete; the plan has released its mutation paths.
- Blocker: none.
- Next action: create a successor Work Plan for persisted aliases, conversation history, relationship learning, LiveKit rooms, and autonomous tuning. Repeated per-turn p95 latency and in-flight Metal-kernel cancellation remain successor evidence, not retroactive claims here.
