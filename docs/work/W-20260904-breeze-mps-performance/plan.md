---
type: Work Plan
title: Breeze TTS Performance on Apple Silicon
description: Breeze TTS Performance on Apple Silicon for bounded M3 Ultra implementation and evidence.
tags: [work, breeze, performance, mps]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T19:40:00Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance
  authority: coordination
  repository_paths: [vendor/breeze-tts, services/breeze, python/simo, web, tests, docs]
  owner: process:simo-performance-integration
  work:
    schema_version: 1
    id: W-20260904-breeze-mps-performance
    state: active
    mode: mutation
    priority: p1
    accountable: process:simo-performance-integration
    created_at: 2026-09-04T22:48:33Z
    updated_at: 2026-09-05T19:40:00Z
    depends_on: []
    knowledge_refs: [interfaces/breeze-tts, operations/lan-voice-site, governance/DOC-0001-documentation-and-work-management]
    write_paths: [README.md, benchmarks/breeze, scripts/render_breeze_benchmarks.py, tests/python/test_breeze_charts.py, docs/work/W-20260904-breeze-mps-performance]
    next_action: T-025 commit and push the completed T-024 reporting changes to origin/main with normal hooks, verify the remote SHA, then release the publication lease. Preserve open release gates and unrelated work.
    blocker: null
---
# Breeze TTS Performance on Apple Silicon

L-025 acquired2026-09-05T19:40Z: user explicitly requests commit and push. T-025/root process:simo-performance-integration is sole integration/publication owner for the existing T-024 paths above and bounded publication records in this bundle; base local and live origin/main both a5ac3fd7a7acc84a6749610147646778da70f6f7. Commit only reviewed reporting work, run normal hooks, push main and verify remote; fork78a79bbe stays unchanged, unrelated :memory:.ses excluded. No model/audio/browser/benchmark/service/identity changes or release promotion. Read-only T-138 verifies held data/source scope while root updates tracking. Release after publication outcome is recorded; other plans have no overlapping mutation paths.

L-024 released2026-09-05T19:37Z: T-024/A-010 complete, root integration owner, plan active/read_only/no write paths. E-024 and R-135/R-136/R-137 hold data/spec/independent review;11 chart tests, configured parent static checks,168 documentation concepts/zero errors/four existing warning categories, five knowledge tests and diff checks pass. Fork/services unchanged, no commits/pushes; full release/physical/listening gates remain open. Acquisition record below is historical.

L-024 acquisition,2026-09-05T19:06Z: T-024/root `process:simo-performance-integration` was sole writer for README.md, benchmarks/breeze, scripts/render_breeze_benchmarks.py, tests/python/test_breeze_charts.py and this Work Plan, from Simo `a5ac3fd7a7acc84a6749610147646778da70f6f7` with only unrelated untracked `:memory:.ses`. The user requested README performance charts/specifications, a recorded improvement timeline, and removal of Flecs copy. Audit existing local artifacts and generate static repository assets with measurement/provenance limits. Read-only T-135/T-136/T-137 reviewers inspect source/evidence; no engine, dependency, fork, service, profile, benchmark rerun, browser/audio, commit or push changes. Release after reproducibility, source/claim review and documentation checks. Other plans remain read-only.

Implement the approved performance-only plan on this M3 Ultra. [Scope](scope.md), [acceptance](acceptance.md), and [execution](execution.md) govern implementation; [checkpoint](checkpoint.md) is the resumption entrypoint. Historical integration remains in [conversational identities](../W-20260802-conversational-identities/evidence/E-007-breeze-apple-silicon-lan.md).

Scope and acceptance were approved before activation. The former plan has released its mutation paths; this plan has no dependency on unfinished identity features. Runtime and measurements remain authority over this record.
