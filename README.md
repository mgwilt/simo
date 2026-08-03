# Simo

Simo is a macOS-first, open-source realtime voice-agent system. Pipecat owns the latency-sensitive media and inference pipeline, Flecs owns bounded live semantic state, and the repository's OKF 0.2 bundle owns durable reviewable knowledge.

The currently selected local inference defaults are Qwen3-TTS 0.6B CustomVoice 6-bit through MLX-Audio, Parakeet TDT 0.6B v3 through Parakeet MLX, and Qwen3.5 4B 4-bit through MLX-LM. Those providers remain replaceable. Model weights are not downloaded by setup.

## Headless quick start

Requirements: Apple Command Line Tools or Xcode, Python 3.11–3.13, and [uv](https://docs.astral.sh/uv/).

```sh
git submodule update --init --recursive
uv sync --extra runtime
uv run python scripts/build_native.py
uv run simo doctor
uv run simo headless --transcript "hello" --transcript "remember the blue door"
```

The headless command loads no speech or language model. It validates and projects repository OKF concepts into a typed Flecs graph, then drives final transcript frames through a real Pipecat pipeline, a bounded observer mailbox, ordered Flecs world progression, one immutable context injection per turn, deterministic text inference, PCM TTS frames, counters, and clean shutdown. The inference providers are test doubles, so this is not the live model or voice proof tracked by `W-20260802-finish-realtime-agent`.

## Preflight

```sh
uv run simo doctor --json
uv run simo doctor --mode live
```

Headless preflight requires only the native core. Live preflight additionally checks Apple Silicon, the three MLX Python runtimes, local model directories, and Pipecat's NLTK sentence data. Missing live prerequisites are reported without importing model runtimes or loading weights.

Install the optional Apple Silicon inference runtimes before live preflight. This installs code and native libraries, not model weights:

```sh
uv sync --extra runtime --extra inference
uv run --extra inference simo doctor --mode live
```

Environment overrides are parsed once into an immutable configuration:

| Variable | Default |
|---|---|
| `SIMO_MODE` | `headless` |
| `SIMO_CORE_LIBRARY` | auto-discovered under `.build/` |
| `SIMO_MODELS_DIR` | `.models` |
| `SIMO_QUEUE_CAPACITY` | `256` |
| `SIMO_MAX_SEGMENTS` | `64` |
| `SIMO_CONTEXT_MAX_CHARS` | `8000` |
| `SIMO_CONTEXT_MAX_AGE_MS` | `1000` |
| `SIMO_TTS_MODEL` | `mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-6bit` |
| `SIMO_TTS_VOICE` | `Aiden` |
| `SIMO_TTS_STREAMING_INTERVAL_S` | `0.32` |
| `SIMO_STT_MODEL` | `mlx-community/parakeet-tdt-0.6b-v3` |
| `SIMO_TEXT_MODEL` | `mlx-community/Qwen3.5-4B-4bit` |

Runtime configuration, model weights, generated audio, and local caches are ignored by Git. Simo does not log or persist raw audio or transcripts by default; the current headless JSON output intentionally contains the synthetic transcripts supplied on its command line.

## Development checks

```sh
uv run python scripts/build_native.py
uv run python -m unittest discover -s tests/python -v
uv run python scripts/validate_docs.py
uv run python -m unittest discover -s scripts/knowledge/tests -v
git diff --check
```

Start architecture and operating documentation at [`docs/index.md`](docs/index.md). Vendored Flecs, Pipecat, and Knowledge Catalog sources are pinned submodules and are not first-party Simo code.
