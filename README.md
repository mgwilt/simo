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

## Persisted aliases and conversations

Simo stores aliases under the platform application-data directory (`~/Library/Application Support/Simo` on macOS) or an explicit `SIMO_DATA_DIR`/`--data-dir`. Create and inspect an alias without loading the native core or models:

```sh
uv run simo alias create Ada --summary "An analytical conversationalist" --json
uv run simo alias list
uv run simo alias show <alias-id> --json
uv run simo alias revise-persona <alias-id> \
  --summary "A playful analytical conversationalist" \
  --instructions "Use concise examples and gentle humor"
```

Each alias has a stable UUID, immutable persona/runtime-profile versions, a human-readable manifest, and a private portable OKF 0.2 bundle. Export and import preserve those identities and version histories:

```sh
uv run simo alias export <alias-id> ./ada.simo-alias
uv run simo --data-dir /tmp/another-simo alias import ./ada.simo-alias
```

Conversation identity and participant membership are indexed in the same local SQLite store:

```sh
uv run simo conversation create --alias <alias-id> --title "First meeting" --json
uv run simo conversation list --alias <alias-id>
uv run simo conversation show <conversation-id> --json
uv run simo conversation delete <conversation-id> --yes
```

Use `talk` to persist supplied synthetic turns through Pipecat, Flecs, deterministic text inference, and deterministic TTS. The result records final user text, generated assistant text, TTS submission, confirmed spoken text, and the primary review transcript as distinct ordered events:

```sh
uv run simo talk --alias <alias-id> \
  --turn "Hello" \
  --turn "Remember that the door is blue" \
  --json
uv run simo talk --alias <alias-id> \
  --conversation <conversation-id> \
  --turn "Continue after restart" \
  --complete
uv run simo conversation export <conversation-id> ./conversation.json
```

Every persisted `(alias, conversation)` run creates a separate native Flecs world. Its conversation and participants are graph entities carrying stable alias, conversation, participant, and optional transport-participant identities. Pipecat inference receives a bounded immutable snapshot containing those values and recent context; native entity IDs, handles, database connections, and mutable storage objects are never serialized across that boundary. Unknown transcript speakers fail closed for scoped worlds.

This deterministic persisted path opens no audio device and loads no model. It proves ordered recording, review, export, restart reconstruction, and isolated scoped Flecs projections; live-model transcript wiring and WebRTC rooms remain later milestones in `W-20260802-conversational-identities`.

Allow-listed first-person statements such as “My name is …”, “I like …”, “My favorite … is …”, “My goal is …”, and “I will …” are promoted into the speaking alias's private relationship memory. Each claim retains participant, conversation, event, confidence, freshness, correction, and lifecycle provenance in SQLite and a portable OKF concept. Active claims relevant to current participants are projected into typed Flecs memory entities and `about participant` graph relations; inference receives their bounded value snapshots and can recall corrected facts after restart. Corrections supersede prior claims without rewriting history. Credential, permission, policy, and unmatched classes fail closed and never enter alias knowledge.

```sh
uv run simo memory list --alias <alias-id> --status active --json
uv run simo memory show <claim-id>
uv run simo memory correct <claim-id> "Corrected relationship fact."
uv run simo memory forget <claim-id> --yes
```

Memory writes are serialized per alias across local processes. Forgetting physically removes the selected claim and its materialized content. Deleting a conversation also deletes claims derived from its events and regenerates each affected alias bundle. Alias export/import carries retained claims and provenance but does not import conversation history or create access to another alias's storage.

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

After the model-download checkpoint, run the unattended model/VAD proof. It requires MLX Metal but no microphone or speaker. Run live preflight separately before opening local audio:

```sh
uv run simo doctor --mode models
uv run simo prove-models
uv run simo doctor --mode live
uv run simo live
```

`prove-models` loads each configured immutable revision through the same adapter used by the live pipeline. It records cold and warm text, synthesis, and transcription timings; requires an exact synthetic text response and round-trip speech transcript; proves one conditioned Silero utterance; replays the generated speech as simulated speaker echo and requires zero extra turns; and then executes real STT → Flecs context injection → real text → real TTS through Pipecat. It writes only an ignored synthetic `.artifacts/model-proof/tts.wav` and does not open the microphone or speaker.

Use the aggregate-only microphone calibrator to diagnose input level separation:

```sh
uv run simo calibrate-mic
```

Wait quietly until you hear one tone, then speak normally until you hear two tones. Simo measures the ambient phase, detects speech onset, and ends the speaking phase itself, so no visual timing or interaction is required. The command retains only aggregate RMS values, never audio or transcripts. Live mode uses Silero neural VAD rather than this RMS recommendation.

The live pipeline is local microphone → bounded Silero utterance detection and Pipecat interruption → Parakeet STT → Flecs context/OKF projection → Qwen text inference → streaming Qwen TTS → local speaker. `Control-C` tears down Pipecat, PortAudio, Silero, and the native Flecs owner.

Environment overrides are parsed once into an immutable configuration:

| Variable | Default |
|---|---|
| `SIMO_DATA_DIR` | platform application-data directory |
| `SIMO_MODE` | `headless` |
| `SIMO_CORE_LIBRARY` | auto-discovered under `.build/` |
| `SIMO_MODELS_DIR` | `.models` |
| `SIMO_QUEUE_CAPACITY` | `256` |
| `SIMO_MAX_SEGMENTS` | `64` |
| `SIMO_CONTEXT_MAX_CHARS` | `8000` |
| `SIMO_CONTEXT_MAX_AGE_MS` | `1000` |
| `SIMO_TEXT_MAX_TOKENS` | `48` |
| `SIMO_AUDIO_INPUT_DEVICE_INDEX` | system default |
| `SIMO_AUDIO_OUTPUT_DEVICE_INDEX` | system default |
| `SIMO_VAD_CONFIDENCE` | `0.10` |
| `SIMO_VAD_START_RMS` | `0.02` |
| `SIMO_VAD_START_MS` | `32` |
| `SIMO_VAD_STOP_MS` | `320` |
| `SIMO_VAD_PRE_ROLL_MS` | `200` |
| `SIMO_MAX_UTTERANCE_S` | `30` |
| `SIMO_TTS_MODEL` | `mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-6bit` |
| `SIMO_TTS_REVISION` | `7dc92af14613355896fcab13b268c19ede233139` |
| `SIMO_TTS_VOICE` | `Aiden` |
| `SIMO_TTS_STREAMING_INTERVAL_S` | `0.24` |
| `SIMO_STT_MODEL` | `mlx-community/parakeet-tdt-0.6b-v3` |
| `SIMO_STT_REVISION` | `ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15` |
| `SIMO_TEXT_MODEL` | `mlx-community/Qwen3.5-4B-4bit` |
| `SIMO_TEXT_REVISION` | `0e7ffd5c629ef7719d4cbc04069232580bfa9d9c` |

Runtime configuration, model weights, generated audio, and local caches are ignored by Git. Headless and live commands do not persist raw audio or transcripts implicitly. The explicit alias/conversation commands persist text and timing in the selected local data directory, while raw audio remains off. The current headless JSON output intentionally contains the synthetic transcripts supplied on its command line.

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
