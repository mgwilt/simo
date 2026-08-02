---
type: Governance Proposal
title: Simo documentation and work-management architecture
description: Proposes a compact OKF 0.2 profile for durable knowledge, bounded work coordination, agent handoffs, and runtime evidence.
tags: [governance, okf, work-management, agents, realtime, flecs]
status: draft
generated: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:53:21Z }
verified: { by: codex/gpt-5.6-sol, at: 2026-08-02T23:53:21Z }
stale_after: 2026-11-02
sources:
  - id: okf-spec
    resource: ../../vendor/knowledge-catalog/okf/SPEC.md
    title: Vendored Open Knowledge Format 0.2 specification
    last_modified: 2026-08-02
  - id: arcology-profile
    resource: ../../../arcology/Docs/governance/okf-producer-profile.md
    title: Arcology OKF producer profile
  - id: arcology-lifecycle
    resource: ../../../arcology/Docs/governance/knowledge-lifecycle.md
    title: Arcology knowledge lifecycle
  - id: arcology-work
    resource: ../../../arcology/Docs/governance/work-tracking.md
    title: Arcology documentation-native work tracking
  - id: arcology-routing
    resource: ../../../arcology/Docs/governance/agent-context-routing.md
    title: Arcology agent context routing
  - id: arcology-contracts
    resource: ../../../arcology/.agents/skills/orchestrate-arcology/references/contracts.md
    title: Arcology orchestration contracts
  - id: pipecat-runtime
    resource: ../../vendor/pipecat/README.md
    title: Pipecat README at the pinned Simo revision
  - id: pipecat-observer
    resource: ../../vendor/pipecat/src/pipecat/pipeline/worker_observer.py
    title: Pipecat worker-observer implementation at the pinned Simo revision
  - id: flecs-observers
    resource: ../../vendor/flecs/docs/ObserversManual.md
    title: Flecs observer manual at the pinned Simo revision
  - id: flecs-systems
    resource: ../../vendor/flecs/docs/Systems.md
    title: Flecs systems manual at the pinned Simo revision
simo:
  profile_version: 1
  stable_id: DOC-0001
  authority: proposal
  repository_paths: [docs]
  context_threads: [019fc48e-ba33-7053-aa5c-3c41c53ebf37]
  owner: unassigned
---
# Simo documentation and work-management architecture

## Status and evidence boundary

This remains the governing documentation proposal, not a runtime contract. Simo now has an implemented first vertical slice at revision `37ff732`; [the semantic context spine](../architecture/semantic-context-spine.md) defines the promoted runtime ownership and evidence boundary. The pinned dependencies establish available upstream behavior, while the founding task `019fc48e-ba33-7053-aa5c-3c41c53ebf37` supplies broader design intent.

The intended system boundary is:

- Pipecat owns latency-sensitive media transport, frames, conversation pipelines, interruption, and realtime service composition. Its pinned README describes a realtime, composable voice/multimodal pipeline framework.[^pipecat-runtime]
- Flecs owns the proposed live semantic world and bounded context-computation systems.
- An adapter turns selected Pipecat observations into semantic events; a normal pipeline processor requests an immutable context snapshot before inference.
- OKF owns durable, reviewable knowledge. It does not prescribe a runtime or replace domain schemas.[^okf-spec]

No document, Markdown link, Work Plan state, or evidence packet is Flecs runtime state. First-party code, configuration, schemas, tests, and observed execution are operational authority for the behavior they actually establish. Documents explain intent, ownership, decisions, and observed evidence, and must link back to that authority.

## Arcology findings: transfer selectively

Arcology's checkout was inspected read-only on 2026-08-02. It was heavily dirty, so its committed closed knowledge-system plan and stable governance concepts are stronger evidence than current uncommitted conventions.

| Pattern | Simo disposition | Reason |
|---|---|---|
| Separate OKF conformance from a stricter producer profile | Adopt | Arcology makes this distinction explicit; upstream OKF deliberately leaves producer-specific policy open.[^arcology-profile][^okf-spec] |
| Shallow indexes, semantic leaves, and bounded retrieval | Adopt | Direct-child indexes and narrow path routing avoid loading a flat corpus.[^arcology-lifecycle][^arcology-routing] |
| Durable concepts/ADRs separate from Work Plans | Adopt | Coordination history must not silently become product or architecture authority.[^arcology-work] |
| Progressive Work Plan bundles with replace-in-place checkpoints | Adopt, simplified | Separating scope, acceptance, execution, decisions, verification, closure, and evidence makes work resumable without a transcript-shaped record.[^arcology-work] |
| Compact task briefs, result packets, and explicit mutation leases | Adopt | The contracts make authority, evidence, and stop conditions inspectable while keeping agent outputs bounded.[^arcology-contracts] |
| Parallel read-only research, one mutation/integration owner, independent verification | Adopt | This permits future parallelism without ambiguous ownership of repository state. |
| Exact token ceilings and repeated full metadata on every Work Plan part | Modify | Prefer semantic splitting and warnings; inherit bundle coordination metadata from `plan.md` to reduce repetition. |
| Unreal/GAS/Mass/CommonUI rules, editor leases, PIE/packaged evidence vocabulary, `arcology.*` fields | Do not copy | These are Arcology product and tooling constraints, not general OKF or Simo requirements. |

## Upstream OKF contract versus the Simo profile

Upstream OKF 0.2 requires only parseable YAML frontmatter with non-empty `type` on non-reserved Markdown concepts, plus valid present `index.md` and `log.md` structures.[^okf-spec] `index.md` and `log.md` are the only reserved names. The OKF concept ID is its bundle-relative path without `.md`; moving a file changes that ID. Unknown types and extension fields must remain consumable.

Everything below is proposed **Simo producer policy**, not an upstream requirement:

- Every concept requires `title`, one-line `description`, non-empty `tags`, explicit `status`, truthful `generated`, and a `simo` mapping.
- `simo` requires `profile_version`, durable `stable_id`, `authority`, relevant `repository_paths`, and a truthful `owner` or `unassigned`.
- Externally derived claims require stable `sources[].id` values and matching claim footnotes keyed to those IDs. `generated`, `verified`, source modification, and `stale_after` remain distinct clocks.
- Consumers preserve unknown keys. Simo validation may report broken internal links and missing index coverage even though general OKF consumers must tolerate them.
- Token counts are diagnostics, not conformance failures: warn when a concept should be split, then require a rationale only if an atomic document intentionally stays large.

## Recommended directory architecture

Create directories only when they gain a real owner or concept; the tree is a contract, not a scaffolding quota.

```text
docs/
  index.md
  product/                    # product briefs and user-visible invariants
    index.md
  architecture/               # current/proposed system ownership and contracts
    index.md
    realtime-agent.md
    flecs-world.md
    context-boundary.md
  decisions/                  # durable ADR-NNNN records
    index.md
  governance/                 # Simo producer profile and operating policy
    index.md
    documentation-profile.md
    work-management.md
    evidence-and-trust.md
  references/                 # mirrors or locks external normative material when needed
    index.md
  work/
    index.md                  # active/review/blocked only
    archive/
      index.md                # terminal-plan links grouped by year
    W-YYYYMMDD-slug/
      index.md                # bounded route, no lifecycle metadata
      plan.md                 # bundle identity, state, owner, paths, next action
      scope.md
      acceptance.md
      execution.md
      checkpoint.md           # replaced with current resumable state
      decisions.md            # work-local decisions and promotion candidates
      verification.md
      closure.md
      tasks/                  # create only for delegated/parallel work
        index.md
        T-NNN.md              # compact task brief
      results/
        index.md
        R-NNN.md              # compact result packet
      evidence/
        index.md
        E-NNN-slug.md         # semantic evidence, not raw logs
```

Indexes list direct children and one-line descriptions only. Search and path routing should begin with Git-native links and frontmatter; add a generated route command only after corpus size justifies tooling. Logs are optional and record only major scope-level changes; Git retains fine-grained history.

## Concept and authority types

Use a small descriptive vocabulary and let unknown types degrade gracefully:

- Durable authority: `Product Brief`, `Architecture Concept`, `Interface Contract`, `Governance Policy`, `Decision Record`, `Operational Playbook`.
- Coordination: `Work Plan`, `Work Scope`, `Work Acceptance`, `Work Execution`, `Work Checkpoint`, `Work Decision Log`, `Verification Record`, `Work Closure`, `Task Brief`, `Result Packet`.
- Evidence and source material: `Evidence Record`, `Reference`, and, only where its full contract is implemented, upstream `Attested Computation`.

`simo.authority` is one of `product`, `architecture`, `interface`, `governance`, `operations`, `coordination`, `evidence`, `reference`, or `proposal`. Coordination and evidence may support authority but never override it.

## Stable IDs and links

- Preserve OKF's path-derived concept ID as the portable identifier.
- Use `simo.stable_id` as a Simo alias that survives a semantic move: `DOC-NNNN` for general concepts and `ADR-NNNN` for durable decisions. Leave a deprecated tombstone at an old path when inbound references matter.
- Work IDs are `W-YYYYMMDD-slug`; reject duplicates.
- Within one Work Plan, use `A-NNN`, `T-NNN`, `D-NNN`, `R-NNN`, and `E-NNN`. Cross-bundle references use the qualified form, for example `W-20260802-docs#A-001`.
- Markdown links remain directed, untyped documentation relationships under OKF. Typed Flecs relationships must come from first-party runtime schemas or code; docs may describe them but cannot instantiate them.

## Work lifecycle and contracts

Use `proposed -> ready -> active -> review -> done`, plus `blocked` and `cancelled`. Keep OKF `status` (`draft`, `stable`, `deprecated`) separate from `simo.work.state`; the first describes document consumption and the second work execution.

`plan.md` owns work identity, accountable owner, mode (`read_only` or `mutation`), dependencies, `repository_paths`, intended `write_paths`, state, next action, and blocker. Intended paths reveal scope and collisions; they do not authorize mutation.

A Task Brief contains one measurable objective, concise context digest, in/out scope, locked decisions, exact inputs, read/mutation authority, allowed paths, dependencies, acceptance IDs, evidence required, stop conditions, and return contract. A Result Packet contains outcome, concise summary, artifact references, bounded findings with confidence and evidence, changed paths, verification results, knowledge-promotion candidates, work IDs advanced, assumptions, unresolved items, and next action. Store raw logs outside the packet and reference them by path or immutable artifact ID.

Evidence Records state: base revision and dirty paths; claim; method/command or runtime operation; result; artifacts/hashes where useful; `proves`; `does_not_prove`; freshness; and verifier. Documentation validation proves documentation structure, never realtime latency, deterministic replay, tool correctness, or deployed behavior.

Closure requires checked acceptance and execution, proportional evidence for every claimed outcome, resolved or explicitly deferred decisions, truthful verification, durable knowledge promotion, and a commit/PR reference or explicit no-publication reason.

## Parallel-agent and ownership model

- One accountable Work Plan owner maintains scope and resolves decisions.
- Read-only research, mapping, and review may run in parallel through bounded Task Briefs.
- One integration owner holds the repository mutation lease at a time. The lease records holder, base state, exact allowed paths, and whether commit/publication is authorized.
- A separate knowledge owner promotes accepted results into durable concepts. Initially this may be the same person as the integration owner, but the roles remain explicit.
- Independent verification begins after the mutation lease is released or on an immutable revision.
- A worker reports a compact blocker instead of expanding scope. Credentials, destructive operations, external publication, deployment, and authorization changes return to the user.

This is intentionally conservative for the repository's first phase. Path-disjoint concurrent writers can be considered later only after collision detection and merge ownership are executable rather than aspirational.

## Realtime-agent and Flecs documentation contract

The founding design uses a two-speed architecture. Pipecat observers can enqueue frame observations without blocking the main pipeline, but the pinned implementation creates an unbounded `asyncio.Queue` per observer.[^pipecat-observer] Simo should therefore document a bounded, filtering semantic-event bridge and make backpressure/drop policy a first-party interface contract before implementation.

Flecs observers are reactive queries suited to infrequent structural changes; the upstream manual warns that they have query cost, cannot process events on multiple threads, and systems are generally more predictable for recurring work.[^flecs-observers] Flecs pipelines and staging support ordered systems, synchronization points, and per-thread command queues.[^flecs-systems] Therefore architecture concepts should distinguish:

- proposed Flecs entities/components/relationships from implemented schemas;
- structural observers from recurring context systems;
- bounded deterministic world updates from external I/O and inference;
- live mutable entities from immutable `ContextSnapshot` values consumed by the voice path;
- durable OKF concept IDs from disposable runtime entity IDs and relation handles.

Document each implemented runtime concept with its source/schema `resource`, owning module, lifecycle, serialization boundary, queries/systems that read or write it, and evidence revision. Graph diagrams are explanatory views. If generated from runtime inspection, label the revision and method; otherwise label them `proposed`.

## Validation rules

Implement validation in layers so reports never blur portable conformance with Simo policy:

1. **OKF:** frontmatter/type, reserved index/log structure, optional-family shapes, actor conventions, and the full `Attested Computation` contract when that type appears.
2. **Simo metadata:** required profile fields, unique stable IDs, truthful explicit lifecycle, valid source/footnote joins, direct-parent index coverage, and valid repository paths.
3. **Work:** valid states and transitions, dependency completion, unique scoped IDs, acceptance/task references, blocker completeness, no overlapping active mutation paths, and evidence-backed closure.
4. **Authority:** coordination docs cannot claim canonical runtime state; `stable` architecture claims require first-party resource links and proportional verification.
5. **Context:** report whole-file token counts and warn at a configurable threshold; recommend semantic splitting and bounded previews without failing an otherwise valid bundle solely for length.

## Archival policy

Never move a terminal plan merely because it aged; moving changes OKF concept IDs. Keep the plan at its original path, remove it from active listings, and link it from `work/archive/index.md` under its terminal year. Keep decisions and evidence needed to interpret released behavior. Deprecate with a replacement link rather than delete when inbound links or historical value remain. Raw reproducible logs may follow a separate retention policy; preserve the compact Evidence Record and immutable artifact reference after raw expiration.

## Minimal implementation plan and acceptance

1. **Accept the profile.** Resolve the five decisions below and promote this draft into separate stable governance concepts.
2. **Add deterministic validation.** Start with OKF/Simo metadata, links, indexes, IDs, and source-footnote joins; add Work Plan transition/collision gates before the first mutation plan.
3. **Create first architecture leaves.** Document the Pipecat/Flecs/OKF boundary, semantic-event bridge, and context-snapshot contract as proposed concepts tied to the pinned dependency revisions.
4. **Pilot one Work Plan.** Use the structure on the first vertical slice; measure retrieval size and handoff quality before building more automation.
5. **Add agent routing.** Keep root guidance short: inspect status, start at `docs/index.md`, retrieve narrowly, preserve vendor/user state, use briefs/results for delegation, and serialize mutations.

Acceptance criteria:

- The validator reports OKF conformance and Simo-profile diagnostics separately.
- An agent can find the governing concept and active work from two shallow index reads, without loading all work history.
- Every Work Plan acceptance item links to a bounded Evidence Record that states both proof and limits.
- No document describes proposed Flecs state as implemented or treats OKF links as runtime relations.
- Parallel read-only tasks can proceed from briefs while one explicit owner controls repository mutations.
- Closing a Work Plan requires evidence, knowledge promotion, and a publication reference or truthful no-publication reason.

## Remaining decisions

1. Assign the initial documentation and work-system owner.
2. Choose whether `DOC-NNNN` aliases are worth maintaining before concepts begin to move; `ADR-NNNN` and Work IDs should remain.
3. Set token warning thresholds after measuring the first real concepts; do not make length alone a conformance failure.
4. Decide raw evidence retention based on privacy, reproducibility, and storage cost.
5. Select the Python/C++ integration boundary before promoting any Pipecat-to-Flecs design from proposal to architecture authority.

[^okf-spec]: `vendor/knowledge-catalog/okf/SPEC.md:10-17, 44-67, 73-80, 134-149, 153-225, 277-282, 347-368, 409-430, 434-482, 502-549, 553-560, 718-759`.
[^arcology-profile]: `/Users/mike/projects/arcology/Docs/governance/okf-producer-profile.md:26-53` (working-tree snapshot; Arcology-specific rules are explicitly separated from OKF).
[^arcology-lifecycle]: `/Users/mike/projects/arcology/Docs/governance/knowledge-lifecycle.md:31-41` (working-tree snapshot).
[^arcology-work]: `/Users/mike/projects/arcology/Docs/governance/work-tracking.md:24-44` and `/Users/mike/projects/arcology/.agents/skills/track-arcology-work/SKILL.md:35-75` (working-tree snapshot; the closed knowledge-system plan is committed evidence).
[^arcology-routing]: `/Users/mike/projects/arcology/Docs/governance/agent-context-routing.md:29-45` (working-tree snapshot).
[^arcology-contracts]: `/Users/mike/projects/arcology/.agents/skills/orchestrate-arcology/references/contracts.md:1-69, 90-170, 192-225` (working-tree snapshot; some contract content is currently modified).
[^pipecat-runtime]: `vendor/pipecat/README.md:7-29` at submodule commit `b114a367a32166207712e8a9c352215a6e24a0db`.
[^pipecat-observer]: `vendor/pipecat/src/pipecat/pipeline/worker_observer.py:7-12, 46-57, 153-172` at submodule commit `b114a367a32166207712e8a9c352215a6e24a0db`.
[^flecs-observers]: `vendor/flecs/docs/ObserversManual.md:83-111` at submodule commit `fd9e5f67a933b78e82694c0c5c32a761f9d6d36d`.
[^flecs-systems]: `vendor/flecs/docs/Systems.md:668-676, 1084-1114` at submodule commit `fd9e5f67a933b78e82694c0c5c32a761f9d6d36d`.
