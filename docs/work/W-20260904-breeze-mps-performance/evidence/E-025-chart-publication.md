---
type: Evidence Record
title: README chart publication
description: Authorized Simo benchmark reporting commit and push with normal hooks and exact remote verification.
tags: [work, publication, performance]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T19:43:00Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-025
  authority: evidence
  repository_paths: [README.md, benchmarks/breeze, scripts/render_breeze_benchmarks.py, tests/python/test_breeze_charts.py, docs/work/W-20260904-breeze-mps-performance]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# README chart publication

T-025/A-010, explicit user commit/push authorization, L-025/root integration owner. Base local and live origin/main matched a5ac3fd7a7acc84a6749610147646778da70f6f7. Scoped25-file reporting commit [ff7960a43241d1cf671f3d6e0ab8bd2de9cd8f76](https://github.com/mgwilt/simo/commit/ff7960a43241d1cf671f3d6e0ab8bd2de9cd8f76), `docs: chart Breeze performance improvements on Apple Silicon`, was pushed via `git push origin main`. Subsequent `git ls-remote origin refs/heads/main` returned that exact SHA at2026-09-05T19:43Z. This metadata-only checkpoint follows that verified publication; its own revision is supplied by Git, avoiding a self-referential hash.

[R-138](../results/R-138.md) independently verifies all E-024/R-137 held hashes, four-product extraction and11 chart tests. Five public benchmark files contain normalized recorded text/JSON/SVG only; no raw .artifacts, models/audio/private keys, absolute home paths or LAN addresses. Fork gitlink/source stays clean78a79bbe7996f88766ee1885140909ca696c7055. Only unrelated untracked :memory:.ses remains, intentionally excluded.

Normal hooks were not skipped or weakened. Pre-commit: staged whitespace, configured Ruff lint/106-file formatting, ty, BasedPyright, documentation170 concepts/zero errors/four existing advisory categories, five knowledge regressions—all pass. Pre-push: native build/tests,212 Python tests (15.210s), documentation and five knowledge tests—all pass. The test fixture false-completion diagnostics and existing dependency deprecation warnings are not failed gates. No runtime code, service, model, hardware/audio/browser operation or benchmark rerun was added.

Proves: reviewed reporting content is committed and available on origin/main with native/Python/static/knowledge publication gates. Does not prove: new performance measurements, Fast/perceptual/physical/CUDA release acceptance or current service health. Those gates remain unchanged. L-025 released with plan active/read_only; root retains integration ownership, all reviewers terminal. Freshness: this host and remote verification on2026-09-05.
