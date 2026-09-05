---
type: Evidence Record
title: Mobile listening and server-recorded results
description: Mobile listening and server-recorded results with bounded CLI evidence and explicit physical acceptance limits.
tags: [work, breeze, listening, mobile]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T15:15:00Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-021
  authority: evidence
  repository_paths: [python/simo/listening_results.py, python/simo/preview_site.py, python/simo/breeze_listening.py, python/simo/cli.py, web/src/listening-review.ts, web/src/preview-only.css, tests/python, web/tests]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Mobile listening and server-recorded results

T-021 implements the user's radio/mobile and server-recording requests. It removes the normal download/upload dependency without changing model, codec, sampling, buffer policy, recipes, identity profiles or Fast acceptance. Root L-020 owns all writes; [R-132](../results/R-132.md)/[R-133](../results/R-133.md) independently hold exact source/test hashes.

## Behavior

One clip's six native Yes/No/Unsure groups replaces24 dropdowns; explicit partial answers are distinguished from unchecked fields. A–D selection, case position, conditions, notes, preferences, observations and every attempt survive server-backed resume. Mobile controls have48px targets, wrapped choices, safe-area padding and reachable Play/Stop; optional trials/notes are collapsed. No autoplay or implicit listening acceptance.

The operator enables --listening-results outside served assets/deck. Private SQLite stores bounded append-only revisions. Opaque session capabilities and exact deck binding identify reports; there is no public listing. The client synchronously retains the newest draft and frozen pending request, coalesces edits and serially retries exact revisions. Saved means latest acknowledgment, not merely a request sent. Conflicts require explicit separate-session saving; storage/offline errors stay visible. An interrupted trial resumes as stopped, never complete. Each fresh attempt retains its original benchmark manifest. Downloads remain optional terminal backups; old pre-upgrade in-page data is not automatically migrated.

## CLI verification

Root194 Python/58 Node/TypeScript/full parent Ruff, format, ty and BasedPyright pass, plus5 knowledge regressions and parent/fork diff checks. Independent review runs19 backend and15 UI fixtures. The first implementation had corrected Python indentation/type/lint errors and Node strip-only parameter-property incompatibility; initial Node run failed before importing this module. All final gates use corrected held source. No dependency upgrade or model execution.

Build: pnpm --dir web exec vite build --config vite.preview.config.ts --outDir ../.artifacts/breeze-performance/preview-listening-mobile-v1. Original web/dist and prior preview assets retained. Actual HTTPS bytes equal build files: JS8b66b5f9a0b7e5b60bd0964582d268dece0b3ede9464d230d06a9a6133eec965; CSS7b1b05047f92f0cf2696614ce5c50f85bf22f6e30adfc31300f41afdd43fc378.

Actual trusted-CA CLI report .artifacts/breeze-performance/listening-mobile-v1/https-results.json SHA6f64238ec6262a98ffa0f4630be6ac5dcff17d6864f02a60a02d9b909a9f25b5 verifies saved revisions1/2/3, exact repeated old writes, restored snapshot equality and no-store responses. One explicitly SYNTHETIC session962d75bc1ddd4f3297d393a15285a081 contains zero ratings and one synthetic running→stopped attempt; it is never listener feedback. Snapshot SHA1ada5c3561f7f4f6017fd803a085704aba9d387e111f90412b5bbffe968a29cb. A separate read-only Python process verified all three SQLite hashes/revisions and0700/0600 modes after the HTTP probe exited. Store-object recreation is also tested; the deployed HTTPS process was not restarted a second time.

Guards: conflicting revision409; missing/cross Origin403; wrong deck409; database/private key/listing404. Limits:256KiB snapshot,512 attempts,2000 revisions/session,32 sessions,48MiB aggregate payload and64MiB SQLite plus journal overhead. No pruning/deletion occurs. Results live in .artifacts/breeze-performance/listening-results-v1/results.sqlite3, not served files or conversational memory.

## Retained services and limits

After idle/no-connection checks, only old HTTPS PID82750/session83932 was stopped intentionally (130). New PID4812/session52322 owns https://192.168.1.83:8444, using existing TLS, preview-listening-mobile-v1 and listening-v2. Deck417e0171a0e3a0b2cb30808da4e5fc1d8b1f5418b7560cb544225698a5a0338c/72 WAVs unchanged. New source/assets produce benchmark manifest2ae86ecbac4f5795c70d08e750383ec758215b60e82cc468d6c0a1dfbcad12d8.

Quality7860 PID46660/runtime7d52e5a4… and experimental7861 PID98272/runtimef0cac89f… remain ready/nonbusy with unchanged last requests api-b561855576f94081bf161641fc9d8c1e and api-e26053849825400ab953544c67662be6. Original8443 PID47503 remains TLS200. No inference request, audio rendering/capture, browser/CUA/Safari, trust changes, commit or push occurred.

This is functional script/HTTP/storage proof, not physical phone layout, accessibility-tree, actual sound onset, intelligibility or quality acceptance. A-001/A-006/A-007 remain open; Quality default and Fast unaccepted. D-012 model/inference/training/full MLX authority remains intact. Next feedback can be read directly from server records; there is no requirement for the user to send a downloaded file.
