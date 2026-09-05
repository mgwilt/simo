---
type: Operational Playbook
title: Serve one Simo alias on a trusted local network
description: Starts, trusts, tests, and stops the fixed-identity HTTPS/WSS browser voice site and mic-free Breeze voice palette.
tags: [operations, lan, https, livekit, breeze, safari]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T16:51:00Z }
sources:
  - id: lan-runtime
    resource: ../../python/simo/lan_site.py
    title: Simo LAN site supervisor
  - id: lan-browser
    resource: ../../web/src/main.ts
    title: Simo browser LiveKit client
  - id: lan-tls
    resource: ../../scripts/setup_lan_tls.py
    title: Simo mkcert setup helper
  - id: breeze-interface
    resource: ../interfaces/breeze-tts.md
    title: Simo Breeze-TTS-2 boundary
  - id: experimental-preview
    resource: ../../python/simo/preview_site.py
    title: Isolated experimental MLX preview service
  - id: https-benchmark
    resource: ../../python/simo/breeze_benchmark.py
    title: Opt-in fixed-corpus uncached HTTPS benchmark
  - id: listening-review
    resource: ../../python/simo/breeze_listening.py
    title: Blinded recorded listening preparation and local export verification
  - id: live-controls
    resource: ../../python/simo/live_controls.py
    title: Bounded session-local conversation overrides
  - id: voice-passages
    resource: ../../python/simo/adapters/livekit/agent_session.py
    title: LiveKit session instructions and Breeze speech grouping
simo:
  profile_version: 1
  stable_id: DOC-0009
  authority: operations
  repository_paths: [python/simo/lan_site.py, python/simo/preview_site.py, python/simo/cli.py, python/simo/doctor.py, scripts/setup_lan_tls.py, services/breeze, web, tests/python]
  owner: codex/gpt-5.6-sol
---
# Serve one Simo alias on a trusted local network

## One-time setup

Install the local server tools and isolated Breeze dependencies, build the browser, and download the pinned models:[^lan-runtime][^lan-browser]

```sh
brew install livekit caddy mkcert
uv sync --all-extras --frozen
uv sync --project services/breeze --frozen
pnpm --dir web install --frozen-lockfile
pnpm --dir web build
uv run python scripts/build_native.py
uv run python scripts/setup_models.py --accept-download
```

Plan the certificate names first, then create and trust the local CA only after reviewing them:

```sh
uv run python scripts/setup_lan_tls.py
uv run python scripts/setup_lan_tls.py --accept-install
```

`mkcert -install` changes a trust store and may require an interactive macOS administrator password. If automation cannot complete it, run that command yourself in Terminal and rerun the setup helper. Never copy `rootCA-key.pem`; it is the private signing key.

For iPhone or iPad, transfer only mkcert's `rootCA.pem` to the device, install the downloaded profile under Settings, then enable full trust under **Settings → General → About → Certificate Trust Settings**. This is a manual security decision on each device. Remove the profile when LAN testing is finished if continuing trust is unnecessary.

## Start

### Live conversation settings

The conversation page has separate conversation and voice instruction textareas plus radio-button response budgets. Tap **Apply now** to use the revision for subsequent LLM and speech-generation jobs without reconnecting; a reply already underway keeps its snapshots. These are settings for the running server only: reload the page to fetch current settings, and restart the server to restore the saved persona/voice and startup budget. No immutable alias versions are edited. The default `SIMO_TEXT_MAX_TOKENS` is512; the page allows bounded64–2048-token overrides. Budgets are ceilings, not promised lengths. If a persona explicitly asks for brief answers, replace that instruction in the conversation field.[^live-controls]

Voice examples below the form are samples, not a selection of the conversation voice. Breeze receives the current voice instruction with the existing fixed CFG/seed. Be specific about register, accent, age, texture and pace, but instruction-only Fast generation is not a locked speaker. Simo groups ordinary replies into one Breeze request, splitting long text losslessly into passages of at most600 characters to reduce sentence-level voice resets. Generation still streams PCM and remains cancellable. These bounds are not an EOS or perceptual-identity guarantee.[^voice-passages]

`GET /api/controls` reports the active prompt, voice instruction, budget, revision, edit capability, CFG and seed. `PUT` accepts exactly `prompt`, `voice_instruction`, `max_tokens` and the current `revision`; it requires JSON and an exact HTTPS Origin matching an allowed Host/port. Stale revisions return409, invalid input400, oversized bodies413, and upload timeouts408. Controls are available to trusted-LAN visitors; this is not multi-user authentication. No endpoint/model/policy changes are exposed. Errors preserve the form's edits; **Reload settings** discards the draft and fetches the active revision.[^live-controls]

### Launch commands

Start the loopback Breeze service in one terminal:

```sh
services/breeze/.venv/bin/python services/breeze/serve.py \
  .models/Breeze-TTS-2 --host 127.0.0.1 --port 7860 --device mps
```

In a second terminal, verify prerequisites, create or choose an alias, then start the site:[^breeze-interface][^lan-tls]

```sh
uv run simo breeze doctor
uv run simo doctor --mode live
uv run simo alias list
uv run simo serve --alias <alias-id> \
  --cert .artifacts/lan-tls/simo-lan.pem \
  --key .artifacts/lan-tls/simo-lan-key.pem
```

Open the printed `https://<mac-name>.local:8443` URL from one trusted device on the same private network. **Mic-free preview** cards deliver the same line with three visible instructions into bounded AudioWorklet PCM storage. The browser buffers the complete clip before starting, so slow generation does not repeatedly interrupt speech. The status shows buffered audio duration; an uncached preview can take tens of seconds, while completed clips are cached for quick replay. This is a smoothness tradeoff, not realtime inference acceptance. The worklet holds at most120 seconds (11.52MB Float32 PCM) and never starts empty, partial or oversized output. **Stop** works while buffering or playing and cancels delivery/generation; failed/cancelled/truncated output is never cached. Completed WAVs remain available through the legacy endpoint. Cache keys include actual runtime/model fingerprints, CFG, instruction and seed. No microphone permission or room connection is needed.[^lan-browser]

## Isolated experimental MLX previews

For an operator-authorized **manual Fast trial**, the existing MLX eight-bit candidate can also serve the full conversation app: start the candidate below, then prefix the normal `simo serve` command with `SIMO_BREEZE_ENDPOINT=http://127.0.0.1:7861/v1/audio/speech`. Select an existing schema-v2 Breeze voice_design alias with CFG4 and uint32 seed; do not revise an immutable profile merely to change its endpoint. Full Simo uses LiveKit incremental PCM, not the preview worklet reserve. This manual use does not declare formal acceptance or enable the reserved released-Fast selector. [Current launch and exact commands](../work/W-20260904-breeze-mps-performance/evidence/E-022-fast-manual-run.md) use the existing Breeze Preview alias on8443, with normal local conversation persistence.[^breeze-interface][^lan-runtime]

The current working tree additionally supports a preview-only MLX experiment without starting a second conversation server. It is not accepted Fast. Keep Quality on7860 and the normal UI on8443; use separate ports and assets. With the existing pinned local model and cached MLX0.32.0 overlay, start the candidate in one terminal:[^experimental-preview][^breeze-interface]

```sh
PYTHONPATH=vendor/breeze-tts UV_CACHE_DIR=/private/tmp/simo-uv-cache \
uv run --offline --project services/breeze --frozen --with mlx==0.32.0 \
  python services/breeze/serve.py .models/Breeze-TTS-2 \
  --host 127.0.0.1 --port 7861 --device mps --experimental-recipe mlx-int8-v1
```

Build only the separate preview output, then start its HTTPS listener in another terminal. Replace the address and certificate paths with existing, trusted values; the certificate must cover the current LAN address or selected `--hostname`.

```sh
pnpm --dir web build:preview
SIMO_BREEZE_ENDPOINT=http://127.0.0.1:7861/v1/audio/speech \
UV_CACHE_DIR=/private/tmp/simo-uv-cache TIKTOKEN_CACHE_DIR=.cache/tiktoken \
uv run --frozen simo breeze serve-preview --node-ip 192.168.1.83 \
  --cert .artifacts/breeze-performance/tls/lan.pem \
  --key .artifacts/breeze-performance/tls/lan-key.pem \
  --assets .artifacts/breeze-performance/preview-site --https-port 8444
```

Open the printed URL, currently `https://192.168.1.83:8444`, only on the trusted LAN. Direct HTTPS uses the existing certificate; it does not install trust, run Caddy/LiveKit, issue sessions, persist conversations, or load STT/LLM models. Exact Host/same-origin checks protect preview routes; the asset allowlist excludes source and keys. Only these built preview assets are served; `web/dist` remains untouched. Without an explicit streaming selection the page buffers the complete clip. Stop cancels buffering/playback, and Ctrl-C releases the separate listener.[^experimental-preview]

For the measured MLX candidate, append `--streaming-runtime <exact-runtime-fingerprint-from-health>` to the HTTPS command. Select only a fingerprint whose producer and playback tests have been reviewed. This operator-only option advertises `mlx-stream-v1`: a640ms startup/rebuffer reserve and two-second posted-minus-consumed worklet queue, still capped at120 seconds of total response audio. The page verifies the fingerprint/policy on each response before posting PCM. A changed runtime fails closed; Quality/default/unknown policies retain complete-clip behavior. The selected experimental fingerprint is currently `f0cac89f955ee07d3f1b1bfac9d2cd8f5a2e1be5dcdb8ae4be828c66cdb24acd`, not an automatically updated or accepted Fast recipe.[^experimental-preview]

Experimental streaming may play some audio before a later network/codec error. Such failures stop and clear queued audio, display the original error and never report completion or cache partial output. The status distinguishes initial buffering from rebuffering and playback; Stop remains available during credit waits. Reload after a separate preview build to load current assets. There is no UI mode selector or change to saved identities. [E-013](../work/W-20260904-breeze-mps-performance/evidence/E-013-progressive-playback.md) records36 tests, exact75-clip simulated playback and actual served policy/cache checks. Fresh full HTTPS cohorts now exist in [E-015](../work/W-20260904-breeze-mps-performance/evidence/E-015-https-corpus-residency.md); real browser/device onset and Fast release remain unverified.[^experimental-preview]

Use the scripted commands below with `SIMO_BREEZE_ENDPOINT=http://127.0.0.1:7861/v1/audio/speech` and the8444 URL for this experiment. Health must report the expected experimental recipe, not Quality or a different backend. Keep the original terminal/environment for rollback. [E-012](../work/W-20260904-breeze-mps-performance/evidence/E-012-experimental-serving.md) records exact source, runtime, TLS/PCM checks and unverified listening limits.

## Scripted performance and preview checks

### User-operated listening review

Prepare a blinded deck from the complete four-arm precision matrix, then append `--listening-deck <deck-directory>/deck.json --listening-results <private-results-directory>` to the isolated preview launch. The results directory must be separate from assets and the deck, have a pre-existing parent, and be private to the operator (0700 directory/0600 database, no symlinks). Keep `--enable-benchmarks` and the exact streaming fingerprint for fresh trials. Preparation performs no inference: all72 full timed WAVs remain unchanged, excluding warmups. Case order and A–D labels are randomized; the cryptographically deck-bound private recipe/ASR key is never served.[^listening-review]

```sh
uv run --frozen simo breeze prepare-listening \
  --comparison .artifacts/breeze-performance/mlx-precision-matrix-v1/comparison.json \
  --expected-sha c3deab334d425ba14e9b694c07a9ec18990126fcce7dce42f02775cb75bc95a5 \
  --output-dir NEW_LISTENING_DIRECTORY
uv run --frozen simo breeze verify-listening \
  --deck NEW_LISTENING_DIRECTORY/deck.json \
  --key NEW_LISTENING_DIRECTORY/private-key.json --ratings DOWNLOADED_RATINGS.json
```

The page shows one clip's ratings at a time, native radio choices and mobile Play/Stop controls. Navigation never plays audio or creates ratings; each play requires a tap. Recorded PCM is fully hash/count-verified before playback. Fresh trials require uncached BYPASS and exact runtime/manifest/request identity; matching producer completion is joined after EOF. Stop/setup failures and all retries are retained, including an interrupted trial recovered as stopped. No microphone or conversational-memory storage is used.[^listening-review]

Ratings, preferences, notes, conditions and attempt diagnostics autosave to the local server; no mobile download/upload is needed. “Saved on this server” means the latest revision was acknowledged. The same browser retains its opaque session capability and offline draft for refresh recovery. Connection/storage errors stay visible with Retry; conflicting tabs require explicitly saving a separate session. Browser storage failure removes automatic recovery, so keep that page open until saved. Clearing site data loses the resume capability, not the server record. Downloads remain an optional terminal backup; they cannot include a running trial.[^listening-review]

Records are append-only revisions in `results.sqlite3`, outside all served files. The JSON GET/PUT route requires a deck-bound opaque128-bit session ID, has no listing endpoint and rejects cross-origin writes. Limits are256KiB per snapshot,512 attempts,2000 revisions/session,32 sessions,48MiB payload and64MiB database (journal overhead is additional). The operator can read the latest snapshot with `ResultsStore.load(session_id)` from `simo.listening_results`, or query the local database; access to the disk is not participant authentication. Preserve synthetic test sessions as explicitly labeled fixtures, not listener evidence. Server saving must be enabled explicitly; without it, the page warns that a download is required.[^listening-review]

Uncertain/missing ratings and ties remain incomplete evidence. Record device/output/network conditions and subjective start/gap observations separately. Browser clocks and worklet drains do not prove acoustic onset or speaker output; paced receipt is not producer RTF and saved clips do not measure synthesis. The verifier checks identity/structure and missing ratings, never accepting Fast automatically.[^listening-review]

No computer-use automation is required. Keep the sidecar idle while each test runs:

```sh
uv run simo breeze benchmark --warmups 3 --limit 10 --seeds 17,29,42 --json
uv run simo breeze benchmark --suite long --warmups 3 --seeds 17,29,42 --audio-dir .artifacts/breeze-long --json
uv run simo breeze verify-preview --url https://<mac-name>.local:8443 --json
pnpm --dir web test
```

The preview probe disconnects one uncached stream, checks lock release/no partial cache, retries, renders all three instructions and compares cached WAV PCM exactly. It requires each streamed/cached response to match the sidecar fingerprint and rejects a changed runtime; schema2 records that binding. It needs at least one uncached preset; use a newly started recipe/source fingerprint rather than deleting unrelated caches. `--ca-file <existing-rootCA.pem>` adds explicit CA verification for a CLI without system trust. `--connect-address <current-private-ip>` routes to that address while still verifying the URL hostname; it does not bypass TLS. Never use an insecure certificate override.

Benchmark JSON separates service first PCM, warmup samples, output duration, frames, total/steady RTF and source/settings identity. `--audio-dir` retains completed listening WAVs and refuses to overwrite them. Browser/worklet timestamps are estimates, not physical first-sound proof. Human listening and device playout remain unverified unless separately observed. Fast startup stays unavailable until the dedicated [performance gates](../work/W-20260904-breeze-mps-performance/acceptance.md) pass.

### Uncached experimental HTTPS corpus

For full transport measurements, append `--enable-benchmarks` to the isolated HTTPS launch with its exact `--streaming-runtime`. This adds a fixed short/long corpus route, absent by default; it never reads or writes the preview cache. Only uint32 seeds and the server-owned `default`, `warm-companion`, `bright-guide` or `grounded-mentor` instruction IDs are accepted. Requests must match the source/build/corpus manifest and runtime fingerprint; completed producer metrics must match the actual response request ID. Source/build changes require a site restart. No arbitrary text or reference inputs are exposed.[^https-benchmark]

```sh
uv run --frozen simo breeze benchmark --url https://192.168.1.83:8444 \
  --ca-file '/Users/mike/Library/Application Support/mkcert/rootCA.pem' \
  --warmups 3 --limit 10 --seeds 17,29,42 --suite short \
  --instruction-id default --audio-dir NEW_DIRECTORY --json
node web/scripts/replay-preview.mjs NEW_DIRECTORY/report.json
```

Choose a new evidence directory for every cohort; use `--suite long` for the two long passages and separate directories for each instruction. Three warmups repeat corpus index0 with the first selected seed and that cohort's instruction. Schema3 preserves the exact schedule, BYPASS, PCM, request-bound stage metrics, arrivals and EOF. Failed attempts retain a report and partial PCM outside the cache and return a failing CLI status; never score only their successful rows. The reader drains without playback pacing. Metrics polling has40 attempts with finite per-request network timeouts, not a strict two-second wall deadline.[^https-benchmark]

Replay validates cohort identity/completeness and actual player/worklet logic using simulated ports, context and render clock. It does not measure physical onset, real network backpressure or another device's Wi-Fi. Repeat control cohorts with the existing evaluated idle-model holder and preserve its before/after timestamps. Do not pool instruction variants or consumer-paced timings into producer throughput acceptance.[^https-benchmark]

The held candidate completed252 timed outputs across separate default short/long and three-instruction control/resident cohorts. HTTPS p95steadyRTF0.685–0.698 and sample-exact replay with zero modeled gaps pass their bounded screens. Seven non-segmentation ASR flags still require quality localization; do not interpret the aggregate speed or cached preview playback as Fast acceptance. Exact commands/settings, failures and hashes are in [E-015](../work/W-20260904-breeze-mps-performance/evidence/E-015-https-corpus-residency.md).[^https-benchmark]

For conversation, click **Start conversation**, grant microphone access, speak, and wait for the status to return to listening after the alias audio. A failed connection may request a fresh token and retry. Every token remains scoped to the same room and fixed `simo-browser` identity; retries do not add another allowed participant identity.

The site exposes HTTPS/WSS on TCP 8443 and LiveKit media on TCP 7881 and UDP 7882. Allow those ports only on the trusted local firewall. Do not configure router forwarding. Breeze, token minting, application data, and LiveKit's internal signaling origin remain loopback-only.

## Stop and review

Use **Disconnect** in the browser, then press `Ctrl-C` once in `simo serve` and once in the Breeze terminal. Review the returned conversation ID with:

```sh
uv run simo conversation show <conversation-id>
```

Raw audio is not retained. Transcript text and timing are retained in Simo's selected data directory.

## Acceptance and troubleshooting

The host-side proof covers certificate-validated HTTPS, static assets, readiness, curated WAV preview generation/cache, request-host signaling selection, retryable fixed-identity token issuance, and clean supervisor shutdown. A complete device acceptance must additionally observe: no certificate warning; microphone permission; connected/listening state; user speech transcription; alias audio playout; interruption while the alias is speaking; disconnect; and a reviewable conversation record.

If the site does not resolve, use a private IPv4 URL only if that current address is included in the certificate. DHCP can change it; the scripted connect-address option preserves an already-certified hostname. Do not bypass certificate warnings. If signaling connects but audio does not, check LAN isolation/firewall access to TCP7881 and UDP7882. Refresh the page after a UI rebuild to load the current playback policy. Slow uncached rendering remains a model-throughput limitation; buffering does not fix realtime inference.

[^live-controls]: `python/simo/live_controls.py`, `python/simo/lan_site.py`, `web/src/live-controls.ts`, and `tests/python/test_live_controls.py`; T-011/D-012 in the conversational-identities Work Plan.
[^voice-passages]: `python/simo/adapters/livekit/agent_session.py` and `python/simo/adapters/livekit/providers.py`; the installed LiveKit default previously wrapped each non-streaming provider request with a sentence tokenizer.
[^lan-runtime]: `python/simo/lan_site.py`, `python/simo/cli.py`, and `tests/python/test_lan_site.py` in the implementation based on `f5a039f`; host execution is recorded in `W-20260802-conversational-identities#E-007`.
[^lan-browser]: `web/src/main.ts`, `web/src/preview-player.ts`, `web/public/pcm-worklet.js`, `web/public/pcm-queue.js` and browser tests. Current bounded buffer and host-side asset/cache evidence: [E-006](../work/W-20260904-breeze-mps-performance/evidence/E-006-smooth-preview.md); physical listening is unverified.
[^lan-tls]: `scripts/setup_lan_tls.py` in the implementation based on `f5a039f`; trust-store changes require explicit operator approval.
[^breeze-interface]: [Breeze-TTS-2 boundary](../interfaces/breeze-tts.md), verified 2026-09-02.
[^experimental-preview]: `python/simo/preview_site.py`, `python/simo/lan_site.py`, the CLI and focused tests; isolated build from `web/preview.html` and `web/vite.preview.config.ts`, player/worklet in `web/src/preview-player.ts` and `web/public`. Current working-tree implementation: [E-012](../work/W-20260904-breeze-mps-performance/evidence/E-012-experimental-serving.md) for serving and [E-013](../work/W-20260904-breeze-mps-performance/evidence/E-013-progressive-playback.md) for opt-in progressive policy. No Fast or physical-playback promotion.
[^https-benchmark]: `python/simo/breeze_benchmark.py`, `python/simo/preview_site.py`, request-scoped metadata in `python/simo/inference.py`, CLI and focused tests, and `web/scripts/replay-preview.mjs`. T-015 working-tree implementation; completed runtime and regression evidence belongs to the dedicated performance Work Plan, not an automatic Fast promotion.
[^listening-review]: `python/simo/breeze_listening.py`, `python/simo/listening_results.py`, `python/simo/preview_site.py`, CLI, `web/src/listening-review.ts`, `web/src/preview-player.ts` and focused Python/Node fixtures. T-019/T-021 working-tree implementation; user listening and physical playback remain separate acceptance gates.
