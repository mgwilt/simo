---
type: Evidence Record
title: Fixed-corpus uncached HTTPS benchmark contract
description: T-015 opt-in transport measurement, source identity, bounded admission and cleanup checks without physical playback acceptance.
tags: [work, breeze, benchmark, https]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T09:37:00Z }
sources:
  - id: starlette-requests
    resource: https://github.com/kludex/starlette/blob/main/docs/requests.md
    title: Starlette streaming request-body documentation
  - id: starlette-responses
    resource: https://github.com/kludex/starlette/blob/main/starlette/responses.py
    title: Starlette StreamingResponse implementation
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-014
  authority: evidence
  repository_paths: [python/simo, tests/python, web/scripts, docs]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Fixed-corpus uncached HTTPS benchmark contract

T-015/D-017 under L-011; root sole writer. Claim: the isolated experimental site can measure fresh fixed-corpus responses without touching completed-preview caches, and bind every completed result to actual runtime/request identity. This is measurement infrastructure, not Fast or physical acceptance. Full cohort and lifecycle results are recorded separately in E-015.

## Source and runtime boundary

Simo base2ffe040c322139174ffd8269625c8a34dcd66ccd plus preserved dirty work; parent/fork gitlink a294fe402eda72b7330dd30fd977c829e72137db. No fork/model/codec/reference/dependency/identity changes in T-015. New `python/simo/breeze_benchmark.py` and focused test; edits to preview_site, inference request metadata, CLI, transport test and replay CLI. No commit/push/publication, normal UI rebuild, Quality restart or trust change. The existing experiment remains runtime f0cac89f955ee07d3f1b1bfac9d2cd8f5a2e1be5dcdb8ae4be828c66cdb24acd, executable d4ba5fd38b69b2f1448e8f5c80ddf13ef07da76c281fc532f7df476417e7c273; model, MLX0.32.0/Metal artifacts and unchanged reference lock are pinned in [E-012](E-012-experimental-serving.md).

Held SHA256:

| Path | SHA256 |
|---|---|
| python/simo/breeze_benchmark.py | cbd92d7ee6db83650074e3d73be73d6725ca1ec38f8eb6c563d57dcf352e7d70 |
| python/simo/preview_site.py | e4c5d403055e962feebcea8be3f540f31dcd1e7a0ca524250f6b2c3d5d21c65a |
| python/simo/inference.py | 41bd3a52432dc1f755dd47797f8f66a877e6a002cfd3b5331443836f6b4574cf |
| python/simo/cli.py | fd42ce846c92a7b41ca65c680b536f4165b097d0f44fd3044e9fa4a91ae5f94f |
| tests/python/test_breeze_https_benchmark.py | 4da027465d1064e1a4b0ee11dbab8acd5c23ecf6d6e86eb69f98b63748e22d47 |
| tests/python/test_breeze_transport.py | ee86c4775c26fd5de36a54b4022284ffe0473f0b4a83301e8ebb45d663a1093a |
| web/scripts/replay-preview.mjs | 2c5afc3a2a0160bb976fe1cdc084452ed985ad770a7186f4ae537ee1b28662e3 |

The canonical manifest SHA3f74496a70b633e9b29b7a4615808662acc49bd61a0b1ccc381a0fa89645868a covers fixed suites/instructions/CFG4, runtime/policy, six listed Python sources and seven retained build files. It does not cover every transitive module. Source/build bytes are checked per request; changes fail closed until restart. Old hashed build assets remain present, not deleted. Actual manifest file `.artifacts/breeze-performance/mlx-https-v1-manifest.json` SHA941bf7dffed35679519f29f52b596b36334b40e6d969ffc80ca6cea53e836a6b.

Main client/site environment: Python3.13.7, macOS26.5.2 arm64, FastAPI0.141.1, Starlette1.6.0, Uvicorn0.52.4, AnyIO4.14.2 and httpx0.28.1. Environment report `mlx-https-v1-environment.json` SHAac262fb1ffd0dd89b2bc2a9d5acdbbe6b367286e51445525df045a75088dd61c. Main uv.lock70af8b76a43cb0e7fefc88ce1d9e58cdee3e8eaa06cabcde00700e351e3741be and pyproject15cf99e93335b304750929cd5f179728f4e2d0d2882afd8786b7421c38a58438 are unchanged. Main dependencies are not a migration of the separate Breeze/codec Transformers4.57.3 lock.

## Implemented contract

- Startup-only `serve-preview --enable-benchmarks` requires explicit exact `--streaming-runtime`. Absent by default. Fixed short/long indices, known instruction IDs and strict uint32 seeds only; reject arbitrary text/reference/duplicate JSON fields, oversized/chunked bodies above1024 bytes, queries, bad content metadata and stale identity.
- Manifest/PCM/metrics routes use the existing Host/Origin boundary, no-store, shared serialization and a fresh synthesizer per request. The normal inference loopback allowlist is unchanged. Benchmark BYPASS never reads or writes preview caches.
- The response monitors disconnect independently on ASGI2.3 and2.4, including before headers. First PCM and a validated actual `api-` request ID precede success headers. Pre-header empty/failure returns502; late failures remain incomplete. Shielded generator close precedes exactly-once lock release. No general concurrently shared synthesizer guarantee is claimed.
- `breeze benchmark --url ...` verifies HTTPS/SNI and a private/loopback numeric destination, exact corpus/settings/manifest and response identity. New evidence directories are exclusive. Noncoalescing arrival timestamps precede copying; EOF wall excludes later metrics polls. Matching completed/EOS/noncancelled producer totals must equal retained PCM before scoring.
- Three warmups repeat index0/first selected seed/cohort instruction. Schema3 keeps all scheduled timed rows, warmups, arrivals, PCM, request-bound metrics and failure/partial evidence. Failed cohorts return a failing status and no success percentiles; never filter down to successful rows. Metrics polling has40 finite attempts, not a strict two-second wall deadline.
- Replay validates schema3 completion, exact schedule/warmups, unique IDs, BYPASS and completed metrics before actual-player/worklet simulation. Older producer/schema2 evidence remains supported and explicitly marks synthetic wire identity when applicable.

## Verification

Before immutable corpus measurement:147 full Simo Python tests,36 web tests, TypeScript and full parent Ruff check/format/ty/BasedPyright pass. Ten new benchmark tests cover admission, both ASGI versions, stale identities, empty/pre-header faults, exact schedules, odd wire alignment, exclusive evidence, partial failures, completed-metric types/totals, private TLS boundary and CLI status. The second transport test covers actual-ID exposure/reset/validation. [R-116](../results/R-116.md) independently passed all12 focused tests plus four CPU failure checks (header/body send, late upstream error, missing ID), each closing its source before one release. No blocking held-source finding.

Actual certificate-verified same-host LAN TLS rejected all14 malformed/unauthorized request variants in `mlx-https-v1-boundary.json` SHAacaec07e699675c87026f6cc8d76cb85c708220df786596ec774ead484ac78ab. Runtime and last request were unchanged before/after: these failures did not run inference. Independent review verified retained report/manifests, not live sockets.

Current-library reference fetched with Context7 outside the sandbox: Starlette Request.stream allows bounded application consumption; StreamingResponse ASGI2.4 catches disconnect during send but does not establish pre-header-stall cancellation.[^starlette-requests][^starlette-responses] The custom watcher/close contract was therefore tested directly against both ASGI branches; no dependency upgrade was needed.

Proves bounded implementation/admission/cleanup and attributed fresh transport measurements at the held source. Does not prove actual browser execution, remote Wi-Fi, physical onset, audible interruptions, matched quality or Fast acceptance. [R-118](../results/R-118.md) identifies the next user-operated acceptance boundary. Verifiers: root and read-only fast_review/buffer_review; exact cohort results and remaining limits follow in E-015.

[^starlette-requests]: Primary Starlette documentation retrieved2026-09-05 with Context7; the application imposes its own1024-byte limit.
[^starlette-responses]: Primary StreamingResponse implementation retrieved2026-09-05; local installed Starlette1.6.0 was also inspected and tested against both ASGI versions.
