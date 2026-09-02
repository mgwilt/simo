---
type: Operational Playbook
title: Serve one Simo alias on a trusted local network
description: Starts, trusts, tests, and stops the fixed-identity HTTPS/WSS browser voice site and mic-free Breeze voice palette.
tags: [operations, lan, https, livekit, breeze, safari]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-09-02T07:02:46Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-09-02T07:02:46Z }
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
simo:
  profile_version: 1
  stable_id: DOC-0009
  authority: operations
  repository_paths: [python/simo/lan_site.py, python/simo/cli.py, python/simo/doctor.py, scripts/setup_lan_tls.py, services/breeze, web, tests/python]
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

Open the printed `https://<mac-name>.local:8443` URL from one trusted Mac, iPhone, or iPad on the same private network. The **Mic-free preview** cards render the same line with three visible voice-design instructions and cache each WAV locally; the first render can take about one minute, while later plays are immediate. No microphone permission or room connection is needed for these cards.

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

If the site does not resolve, open the printed private IPv4 URL instead. If Safari reports an untrusted certificate, do not bypass the warning: install and explicitly trust the CA. If signaling connects but audio does not, check LAN isolation and firewall access to TCP 7881 and UDP 7882. Expect tens of seconds before Breeze audio on the current eager MPS path; this is a measured model limitation, not necessarily a networking failure.

[^lan-runtime]: `python/simo/lan_site.py`, `python/simo/cli.py`, and `tests/python/test_lan_site.py` in the implementation based on `f5a039f`; host execution is recorded in `W-20260802-conversational-identities#E-007`.
[^lan-browser]: `web/src/main.ts`, `web/src/style.css`, and the pinned browser lockfile in the implementation based on `f5a039f`.
[^lan-tls]: `scripts/setup_lan_tls.py` in the implementation based on `f5a039f`; trust-store changes require explicit operator approval.
[^breeze-interface]: [Breeze-TTS-2 boundary](../interfaces/breeze-tts.md), verified 2026-09-02.
