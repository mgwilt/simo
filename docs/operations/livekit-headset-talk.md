---
type: Operational Playbook
title: Talk to one Simo alias through LiveKit
description: Runs and reviews an interactive local headset conversation with one persisted alias through a self-hosted LiveKit room.
tags: [operations, livekit, headset, conversation, macos]
status: stable
generated: { by: codex/gpt-5.6-sol, at: 2026-08-03T16:17:35Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-03T16:17:35Z }
sources:
  - id: local-talk-runtime
    resource: ../../python/simo/livekit_local_talk.py
    title: Simo local LiveKit talk runtime
  - id: talk-cli
    resource: ../../python/simo/cli.py
    title: Simo structured CLI
  - id: live-doctor
    resource: ../../python/simo/doctor.py
    title: Simo LiveKit-native preflight
simo:
  profile_version: 1
  stable_id: DOC-0007
  authority: operations
  repository_paths: [python/simo/livekit_local_talk.py, python/simo/livekit_local_server.py, python/simo/cli.py, python/simo/doctor.py, tests/python/test_livekit_local_talk.py, tests/python/test_cli.py, tests/python/test_doctor.py]
  owner: codex/gpt-5.6-sol
---
# Talk to one Simo alias through LiveKit

## Start

Create or select a persisted alias, verify the LiveKit-native local runtime, then start the conversation:[^talk-cli][^live-doctor]

```sh
uv run simo alias create Ada --instructions "Speak naturally and keep replies concise." --json
uv run simo alias list
uv run simo doctor --mode live
uv run simo talk --alias <alias-id>
```

`talk` starts an ephemeral loopback-only LiveKit server, the selected alias as a LiveKit Agents participant, and a native WebRTC headset participant. It uses the system-default microphone and speaker unless `SIMO_AUDIO_INPUT_DEVICE_INDEX` or `SIMO_AUDIO_OUTPUT_DEVICE_INDEX` selects a LiveKit device index. The ready line names both active devices. Press `Ctrl-C` once for a clean stop.[^local-talk-runtime]

Use `--human-name Mike` to set transcript attribution, `--conversation <conversation-id>` to resume earlier context, `--complete` to mark the conversation complete at shutdown, or `--max-duration-s N` for a bounded run. Raw audio is not retained.

## Review

The command prints its conversation ID when it exits. Review or export final user transcriptions and actually spoken assistant output with:

```sh
uv run simo conversation show <conversation-id>
uv run simo conversation export <conversation-id> ./conversation.json
```

Generated-but-unspoken text remains a diagnostic event and is not substituted into the primary review transcript.

## Current proof boundary

Revision `fac700e` has unit/static coverage for CLI routing, device selection, room/result contracts, and the LiveKit-native doctor. A bounded observed run opened the default Arctis Nova Pro input/output, joined distinct human and alias participant SIDs, published the microphone-source track, shut down cleanly at the duration bound, and retained no raw audio. This proves startup, room attachment, device selection, identity separation, persistence initialization, and bounded shutdown. It does not prove subjective voice quality, a human-spoken transcription, barge-in behavior, or latency targets; those require operator experience or synthetic acoustic acceptance rather than documentation.[^local-talk-runtime]

[^local-talk-runtime]: `python/simo/livekit_local_talk.py`, `python/simo/livekit_local_server.py`, and `tests/python/test_livekit_local_talk.py` at revision `fac700e8141808aa032ccc13c891c6be01af9595`.
[^talk-cli]: `python/simo/cli.py` and `tests/python/test_cli.py` at revision `fac700e8141808aa032ccc13c891c6be01af9595`.
[^live-doctor]: `python/simo/doctor.py` and `tests/python/test_doctor.py` at revision `fac700e8141808aa032ccc13c891c6be01af9595`; observed on the declared M3 Ultra with default Arctis Nova Pro input/output on 2026-08-03.
