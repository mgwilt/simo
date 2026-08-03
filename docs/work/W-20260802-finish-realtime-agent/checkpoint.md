---
type: Work Checkpoint
title: Finish Simo checkpoint
description: Captures the current resumable product-completion state.
tags: [work, checkpoint, product]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T01:51:56Z }
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
- Progress: `T-008` now has the installed/locked PyAudio transport, typed device/VAD configuration, bounded utterance and interruption processor, complete local Pipecat pipeline owner, explicit PortAudio cleanup, checksum-pinned small-data setup, fake-inference worker lifecycle proof, and outside-sandbox device preflight at `7f390b1`. Revision `3be0e37` adds a plan-only-by-default model installer, immutable revisions, free-space checks, required-file validation, atomic completion markers, and doctor enforcement. Real models and audio acceptance remain pending.
- Current audit: direct macOS live preflight passes the M3 Ultra, native core, MLX runtimes and Metal device, PyAudio, Arctis Nova Pro input/output, and Pipecat sentence data. The three pinned model repositories are absent, as intended before authorization.
- Resumed: the user explicitly authorized model downloads on 2026-08-02 local time. The 7,403,765,096-byte pinned transfer into ignored `.models/` storage is now within scope.
- Blocker: none.
- Next action: run the guarded installer, verify the completion markers and doctor, then prove each model before opening the microphone and running the human acceptance session.
