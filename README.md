# Simo

Simo is a macOS-first, open-source realtime voice-agent system. Pipecat owns the latency-sensitive media and inference pipeline, Flecs owns bounded live semantic state, and the repository's OKF 0.2 bundle owns durable reviewable knowledge.

The currently selected local inference defaults are Qwen3-TTS 0.6B CustomVoice 6-bit through MLX-Audio, Parakeet TDT 0.6B v3 through Parakeet MLX, and Qwen3.5 4B 4-bit through MLX-LM. Those providers remain replaceable. Model weights are not downloaded by setup.

## Headless quick start

Requirements: Apple Command Line Tools or Xcode, Python 3.11–3.13, [uv](https://docs.astral.sh/uv/), and PortAudio (`brew install portaudio`) for live microphone/speaker mode.

```sh
git submodule update --init --recursive
uv sync --extra runtime --extra inference
uv run python scripts/build_native.py
uv run python scripts/setup_live_data.py
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
uv run python scripts/setup_live_data.py
uv run --extra inference simo doctor --mode live
```

The live-data setup downloads only NLTK's checksum-pinned 4.3 MB `punkt_tab` tokenizer into ignored `.cache/` storage. Live preflight also verifies MLX Metal and the selected/default PortAudio input and output devices. It remains not ready until all three model repositories exist under `.models/`.

Preview the pinned model plan without downloading anything:

```sh
uv run python scripts/setup_models.py
```

The default plan is a 6.90 GiB transfer and requires at least 10.62 GiB free for downloads plus temporary overhead. After explicitly accepting that large download, install all three immutable revisions with:

```sh
uv run python scripts/setup_models.py --accept-download
```

The installer downloads only the declared repositories, verifies their required files, and writes a local revision marker after each model is complete. Live preflight rejects partial repositories and markers that do not match the configured model ID and revision.

After the model-download checkpoint and successful live preflight, start the local agent with headphones to reduce speaker-to-microphone feedback:

```sh
uv run simo prove-models
uv run simo live
```

`prove-models` loads each configured immutable revision through the same adapter used by the live pipeline. It records cold and warm text, synthesis, and transcription timings; requires an exact synthetic text response and round-trip speech transcript; and then executes real STT → Flecs context injection → real text → real TTS through Pipecat. It writes only an ignored synthetic `.artifacts/model-proof/tts.wav` and does not open the microphone or speaker.

If live mode does not detect a quiet headset microphone, calibrate it before changing the typed threshold:

```sh
uv run simo calibrate-mic
```

Remain quiet during the first prompt and speak continuously during the second. The command retains only aggregate RMS values, never audio or transcripts. It prints a `SIMO_VAD_START_RMS=...` recommendation only when speech is clearly separated from ambient sound; otherwise it fails closed and asks you to check mute and retry.

The live pipeline is local microphone → bounded energy utterance detection and Pipecat interruption → Parakeet STT → Flecs context/OKF projection → Qwen text inference → streaming Qwen TTS → local speaker. `Control-C` tears down Pipecat, PortAudio, and the native Flecs owner.

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
| `SIMO_AUDIO_INPUT_DEVICE_INDEX` | system default |
| `SIMO_AUDIO_OUTPUT_DEVICE_INDEX` | system default |
| `SIMO_VAD_START_RMS` | `0.02` |
| `SIMO_VAD_START_MS` | `60` |
| `SIMO_VAD_STOP_MS` | `500` |
| `SIMO_VAD_PRE_ROLL_MS` | `200` |
| `SIMO_MAX_UTTERANCE_S` | `30` |
| `SIMO_TTS_MODEL` | `mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-6bit` |
| `SIMO_TTS_REVISION` | `7dc92af14613355896fcab13b268c19ede233139` |
| `SIMO_TTS_VOICE` | `Aiden` |
| `SIMO_TTS_STREAMING_INTERVAL_S` | `0.32` |
| `SIMO_STT_MODEL` | `mlx-community/parakeet-tdt-0.6b-v3` |
| `SIMO_STT_REVISION` | `ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15` |
| `SIMO_TEXT_MODEL` | `mlx-community/Qwen3.5-4B-4bit` |
| `SIMO_TEXT_REVISION` | `0e7ffd5c629ef7719d4cbc04069232580bfa9d9c` |

Runtime configuration, model weights, generated audio, and local caches are ignored by Git. Simo does not log or persist raw audio or transcripts by default; the current headless JSON output intentionally contains the synthetic transcripts supplied on its command line.

## Operations and privacy

`simo headless` writes its requested result to standard output and privacy-safe operational events to standard error as JSON Lines with schema `simo.event.v1`. Redirect the streams independently when collecting evidence:

```sh
uv run simo headless --transcript "synthetic test turn" \
  > /tmp/simo-result.json \
  2> /tmp/simo-events.jsonl
```

The event stream records lifecycle transitions, shutdown reason, aggregate stage latency and errors, TTS time to first generated audio, Flecs world revision, and bounded queue depth/drop counters. It never includes transcript text, prompts, generated text, raw audio, exception messages, or model output. The headless result is different: its snapshot intentionally echoes the synthetic command-line transcripts, so treat that output according to the supplied data. Interrupting the command releases the Pipecat pipeline and native world before exiting; the command returns status `130` for a terminal interrupt.

See [runtime operations](docs/operations/runtime-observability.md) for the schema, ownership, and proof limits.

## Development checks

```sh
uv sync --extra runtime --extra inference --extra dev
uv run python scripts/build_native.py
uv run python -m unittest discover -s tests/python -v
uv run pyright
uv run ruff check python/simo tests/python scripts
uv run ruff format --check python/simo tests/python scripts
uv run python scripts/validate_docs.py
uv run python -m unittest discover -s scripts/knowledge/tests -v
git diff --check
```

Start architecture and operating documentation at [`docs/index.md`](docs/index.md). Vendored Flecs, Pipecat, and Knowledge Catalog sources are pinned submodules and are not first-party Simo code.
