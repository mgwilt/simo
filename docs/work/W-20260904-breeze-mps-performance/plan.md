---
type: Work Plan
title: Breeze TTS Performance on Apple Silicon
description: Breeze TTS Performance on Apple Silicon for bounded M3 Ultra implementation and evidence.
tags: [work, breeze, performance, mps]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T18:43:10Z }
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
    updated_at: 2026-09-05T18:48:34Z
    depends_on: []
    knowledge_refs: [interfaces/breeze-tts, operations/lan-voice-site, governance/DOC-0001-documentation-and-work-management]
    write_paths: [README.md, vendor/breeze-tts, services/breeze, python/simo, web, tests, scripts, docs]
    next_action: "T-023 published the owned fork through78a79bb and prepares the matching Simo checkpoint. User tests the manual Fast conversation; the known End conversation server-lifetime coupling remains open and release/physical acceptance is still unclaimed."
    blocker: null
---
# Breeze TTS Performance on Apple Silicon

Implement the approved performance-only plan on this M3 Ultra. [Scope](scope.md), [acceptance](acceptance.md), and [execution](execution.md) govern implementation; [checkpoint](checkpoint.md) is the resumption entrypoint. Historical integration remains in [conversational identities](../W-20260802-conversational-identities/evidence/E-007-breeze-apple-silicon-lan.md).

Scope and acceptance were approved before activation. The former plan has released its mutation paths; this plan has no dependency on unfinished identity features. Runtime and measurements remain authority over this record.
