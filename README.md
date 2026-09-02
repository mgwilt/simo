# Simo

> [!WARNING]
> **Gigaslop ahead.** This repository is a playground for experimenting with local voice
> orchestration, not production-ready software. Expect rough edges, changing interfaces, and ideas
> that may be replaced as quickly as they are tested.

Simo is an experimental local voice-agent runtime for Apple Silicon Macs. It combines a
self-hosted LiveKit audio path, local MLX models, a small native Flecs context core, and local
persistence for conversational identities and memory.

The repository currently includes a command-line interface for headless runs, persisted aliases
and conversations, deterministic text turns, and local headset sessions. It is still a prototype:
interfaces and stored data may change, and the live voice path requires an explicit model download.

## Local model matrix

These are the default models selected in `python/simo/config.py`. Each model ID and revision can be
overridden through the corresponding `SIMO_*_MODEL` and `SIMO_*_REVISION` environment variables.

| Role | Default model | Runtime | Intent |
| --- | --- | --- | --- |
| Speech to text | `mlx-community/parakeet-tdt-0.6b-v3` | Parakeet MLX | Transcribe local microphone or room audio |
| Language model | `mlx-community/Qwen3.5-4B-4bit` | MLX-LM | Generate short, context-aware replies locally |
| Text to speech | `BreezeBlue/Breeze-TTS-2` | Isolated PyTorch MPS service | Generate designed alias speech locally; current eager MPS path is functional but not realtime |
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

The measured M3 Ultra eager path has p95 first audio of 71.87 seconds and p95 RTF of 13.51. It is
kept as the requested default despite missing the preview target; set `SIMO_TTS_BACKEND=qwen` to
use the former MLX-Audio backend in a new process. See the [LAN operation guide](docs/operations/lan-voice-site.md)
for device CA trust, ports, shutdown, and the remaining physical Safari acceptance step.

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
