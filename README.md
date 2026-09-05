# Simo

> [!WARNING]
> **Gigaslop ahead.** This repository is a playground for experimenting with local voice
> orchestration, not production-ready software. Expect rough edges, changing interfaces, and ideas
> that may be replaced as quickly as they are tested.

Simo is an experimental local voice-agent runtime for Apple Silicon Macs. It combines a
self-hosted LiveKit audio path, local MLX models, a small native Flecs context core, and local
persistence for conversational identities and memory.

The repository now includes headless and live voice conversations, persisted aliases and memory,
a trusted-LAN mobile interface, live conversation and voice-direction controls, and a dedicated
Breeze TTS 2 performance laboratory. It is still a prototype: interfaces and stored data may
change, and the live voice path requires explicit model downloads.

## What works now

- One persisted conversational identity can run locally through STT, an MLX language model,
  Breeze speech generation, and LiveKit without sending conversation content to a hosted model.
- The LAN page works as a microphone client or a tap-to-listen interface, with mobile-sized radio
  controls, streaming Stop, completed WAV caching, and server-recorded listening results.
- Conversation instructions, voice instructions, and response-token budgets can be changed with
  **Apply now** and take effect on subsequent turns without rewriting the saved alias.
- The owned [`breeze-tts-mps`](https://github.com/mgwilt/breeze-tts-mps/tree/simo-apple-silicon)
  fork adds incremental MPS output and an experimental hybrid Torch/MLX generation path while
  retaining the upstream CUDA implementation.

The current Apple Silicon candidate flows through:

```text
text + voice instruction
  -> PyTorch BF16 text preparation
  -> MLX int8 backbone and depth generation
  -> stateful codec decoding
  -> bounded PCM streaming
  -> LiveKit or browser playback
```

On the development M3 Ultra, fixed HTTPS control and resident-model cohorts measured p95
steady-state RTF of 0.685–0.698. A separate process-startup cohort measured warm service first PCM
at 0.280–0.304 seconds and launch-to-ready at 8.329–9.157 seconds. These are reproducible engineering
measurements, not physical speaker-onset or perceptual acceptance; the candidate remains explicitly
experimental until the remaining listening gates are completed.

## Local model matrix

These are the default models selected in `python/simo/config.py`. Each model ID and revision can be
overridden through the corresponding `SIMO_*_MODEL` and `SIMO_*_REVISION` environment variables.

| Role | Default model | Runtime | Intent |
| --- | --- | --- | --- |
| Speech to text | `mlx-community/parakeet-tdt-0.6b-v3` | Parakeet MLX | Transcribe local microphone or room audio |
| Language model | `mlx-community/Qwen3.5-4B-4bit` | MLX-LM | Generate context-aware replies with a configurable response budget |
| Text to speech | `BreezeBlue/Breeze-TTS-2` | PyTorch prefill plus MLX candidate; PyTorch rollback | Generate incremental designed speech locally |
| Voice activity detection | Silero VAD | LiveKit Agents Silero plugin | Detect speech turns and interruptions before transcription |

The setup script pins exact revisions and requires an explicit flag before downloading model
weights. Run `uv run python scripts/setup_models.py` to inspect the current plan.

## Why Flecs?

[Flecs](https://github.com/SanderMertens/flecs) is a strong fit for Simo's live semantic state
because an entity-component system makes changing context explicit and composable: conversations,
participants, transcript segments, and memory claims can remain small typed components and
relations, while systems query and update only the shapes they care about instead of growing one
central session object or passing loose dictionaries between stages. In Simo, that means one
bounded in-memory world per conversation, one mutation owner, and revisioned immutable snapshots
at the model boundary, so inference code never receives native entity handles or mutable state.
LiveKit still owns realtime audio, SQLite owns durable local data, and the OKF bundle holds
reviewable project knowledge; the extra native complexity buys a context plane intended to remain
inspectable, scoped, and testable as orchestration behavior grows.

## Requirements

For the headless and deterministic paths:

- macOS
- Python 3.11, 3.12, or 3.13
- [uv](https://docs.astral.sh/uv/)
- Apple Command Line Tools or Xcode

Live voice also requires an Apple Silicon Mac, LiveKit Server, and the optional MLX dependencies
and models described below. Breeze-TTS-2 use is subject to its separate non-commercial model
license.

## Setup

```sh
git clone --recurse-submodules https://github.com/mgwilt/simo.git
cd simo
uv sync --extra runtime
uv run python scripts/build_native.py
uv run python scripts/setup_live_data.py
uv run simo doctor
```

Run a deterministic, no-model turn through the context pipeline:

```sh
uv run simo headless \
  --transcript "hello" \
  --transcript "remember that the door is blue"
```

Create a persisted alias and conversation without opening an audio device:

```sh
uv run simo alias create Ada --summary "An analytical conversationalist" --json
uv run simo talk --alias <alias-id> \
  --turn "Hello" \
  --turn "Remember that the door is blue"
uv run simo conversation list --alias <alias-id>
```

## Live voice

Install LiveKit Server and the optional inference dependencies:

```sh
brew install livekit
uv sync --extra runtime --extra inference
```

Model downloads are opt-in. The first command prints the pinned revisions, expected download size,
and required free space; it does not download anything.

```sh
uv run python scripts/setup_models.py
uv run python scripts/setup_models.py --accept-download
```

Check the local runtime, then start a headset conversation:

```sh
uv run simo doctor --mode models
uv run simo prove-models
uv run simo doctor --mode live
uv run simo talk --alias <alias-id> --human-name "Local user"
```

`talk` starts a loopback-only LiveKit server and uses the system-default microphone and speaker.
Press `Ctrl-C` once to stop. The command prints the conversation ID so the transcript can be
reviewed or exported:

```sh
uv run simo conversation show <conversation-id>
uv run simo conversation export <conversation-id> ./conversation.json
```

See the [headset operation guide](docs/operations/livekit-headset-talk.md) for device selection,
resuming conversations, and the current verification boundary.

## LAN browser voice

The browser site serves one persisted alias to one Mac, iPhone, or iPad on the same trusted local
network. It uses HTTPS/WSS, retryable room tokens for one fixed browser identity, audio-only counterpart allow lists, and
keeps Breeze and internal services on loopback.

```sh
brew install caddy mkcert
uv sync --project services/breeze --frozen
pnpm --dir web install --frozen-lockfile
pnpm --dir web build
uv run python scripts/setup_lan_tls.py
uv run python scripts/setup_lan_tls.py --accept-install

services/breeze/.venv/bin/python services/breeze/serve.py \
  .models/Breeze-TTS-2 --host 127.0.0.1 --port 7860 --device mps

uv run simo serve --alias <alias-id> \
  --cert .artifacts/lan-tls/simo-lan.pem \
  --key .artifacts/lan-tls/simo-lan-key.pem
```

The mic-free cards stream PCM incrementally and support Stop; completed renders remain cached as
WAVs. The live-control panel uses radio buttons for response budgets and voice choices, while
**Apply now** updates the running process immediately. Listening ratings, preferences, notes, and
attempt diagnostics autosave to a private local result store, so phone testing does not require
downloading and re-uploading a report.

Quality remains the default startup mode and preserves requested CFG. The reserved
`--performance-mode fast` selector still fails closed until formal release gates pass, but an
operator can manually test the working `mlx-int8-v1` candidate today. Start it on port 7861:

```sh
PYTHONPATH=vendor/breeze-tts UV_CACHE_DIR=/private/tmp/simo-uv-cache \
uv run --offline --project services/breeze --frozen --with mlx==0.32.0 \
  python services/breeze/serve.py .models/Breeze-TTS-2 \
  --host 127.0.0.1 --port 7861 --device mps \
  --experimental-recipe mlx-int8-v1
```

Then start the normal conversation server in another terminal with the candidate endpoint:

```sh
SIMO_BREEZE_ENDPOINT=http://127.0.0.1:7861/v1/audio/speech \
uv run simo serve --alias <alias-id> \
  --cert .artifacts/lan-tls/simo-lan.pem \
  --key .artifacts/lan-tls/simo-lan-key.pem
```

Use a schema-v2 Breeze voice-design alias with CFG 4 and a uint32 seed. The candidate currently
supports voice design, not reference-audio cloning. `--engine reference` restores full-utterance
generation, and `SIMO_TTS_BACKEND=qwen` selects the former MLX-Audio backend in a new process.

Performance is tracked separately in [Breeze MPS performance](docs/work/W-20260904-breeze-mps-performance/).
See the [LAN operation guide](docs/operations/lan-voice-site.md) for setup, server-recorded listening,
and scripted verification without computer use. One known rough edge remains: **End conversation**
currently stops the supervising `simo serve` process, so restart that command before reconnecting.

## Commands

| Command | Purpose |
| --- | --- |
| `simo doctor` | Check headless, model, or live prerequisites |
| `simo headless` | Run deterministic transcript turns without local models |
| `simo alias` | Create, revise, export, and import conversational aliases |
| `simo conversation` | Create, inspect, export, resume, and delete conversations |
| `simo memory` | Inspect, correct, and forget retained claims |
| `simo talk` | Run synthetic turns or a local LiveKit headset session |
| `simo serve` | Serve one alias to one trusted-LAN HTTPS/WSS browser |
| `simo breeze` | Inspect and benchmark the local Breeze-TTS-2 sidecar |
| `simo lab` | Run bounded LiveKit and multi-alias experiments |
| `simo prove-models` | Exercise the configured STT, text, and TTS models without audio devices |

Run `uv run simo <command> --help` for command-specific options.

## Local data and privacy

Simo stores aliases, conversations, and retained claims in the platform application-data directory
(`~/Library/Application Support/Simo` on macOS). Use `--data-dir` or `SIMO_DATA_DIR` to select a
different location.

Raw audio is not retained. Conversation commands do persist transcript text and timing data, and
headless JSON output includes transcripts supplied on the command line. Runtime caches, downloaded
models, generated audio, and local data are ignored by Git.

## Development

Install the development dependencies and run the repository checks:

```sh
uv sync --extra runtime --extra inference --extra dev
uv run python scripts/build_native.py
uv run python -m unittest discover -s tests/python -v
uv run basedpyright
uv run ruff check python/simo tests/python scripts
uv run ruff format --check python/simo tests/python scripts
uv run python scripts/validate_docs.py
uv run python -m unittest discover -s scripts/knowledge/tests -v
git diff --check
```

The main source directories are:

- `python/simo/` — command-line interface and Python runtime code
- `include/` and `src/` — native Flecs context core
- `tests/` — Python and native tests
- `docs/` — architecture, interfaces, operations, and active work
- `vendor/` — pinned upstream submodules

Start with the [documentation index](docs/index.md) for architecture and operating details.
