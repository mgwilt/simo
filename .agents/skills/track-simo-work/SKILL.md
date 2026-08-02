---
name: track-simo-work
description: Create, resume, update, block, review, close, reopen, or archive Simo's documentation-native OKF Work Plans. Use for multi-file or multi-session implementation, architecture or public-interface changes, coordinated or parallel agents, independent verification, explicit tracking requests, or recovery from a prior checkpoint; skip routine explanations, tiny isolated edits, and untracked exploratory questions.
---

# Track Simo Work

Use one progressive Work Plan bundle as the durable coordination record for significant work. Never turn it into a transcript or a second source of runtime truth.

## Find or create the plan

1. Inspect `git status` and preserve unrelated work.
2. Read `../../../docs/work/index.md` and search non-terminal `plan.md` files for affected `repository_paths` and `write_paths`.
3. Resume a matching plan before creating another.
4. Otherwise create `docs/work/W-YYYYMMDD-kebab-name/` using the exact structure in [references/work-plan-contract.md](references/work-plan-contract.md).
5. Use `read_only` with no write paths for tracked research. Intended write paths expose collisions and scope; they never grant authority or a mutation lease.

Do not create a Work Plan for a short answer, a read-only inspection that will not need handoff, a typo, or one obvious isolated edit.

## Make work decision-complete

- Keep `plan.md` as the small lifecycle entrypoint.
- Put scope, acceptance, execution, current checkpoint, decisions, verification, closure, and semantic evidence in their owning artifacts.
- Create `tasks/` and `results/` only when delegation makes them useful.
- Use stable qualified IDs: Work `W-...`; acceptance `A-NNN`; task `T-NNN`; decision `D-NNN`; result `R-NNN`; evidence `E-NNN`. Refer across bundles as `<work-id>#<local-id>`.
- Replace `checkpoint.md` with current resumable state. Never append conversation history or raw logs.
- Link `knowledge_refs` to the durable concepts governing the work and keep `next_action` current.

Read [references/work-plan-contract.md](references/work-plan-contract.md) before creating a bundle, delegating tasks, changing lifecycle state, or closing work.

## Advance lifecycle safely

Use `proposed -> ready -> active -> review -> done`, with explicit `blocked` and `cancelled` paths.

- Require decision-complete scope and acceptance before `ready`.
- Require dependencies satisfied and an explicit owner before `active`.
- Do not activate mutation work whose exact or ancestor/descendant write path overlaps another active mutation plan.
- In coordinated work, allow parallel read-only tasks but keep one integration owner and one active repository mutation lease.
- Record blocker reason, attempted routes, needed input/state, owner, and next action.
- Reopen terminal work with a reason; do not rewrite its prior outcome.
- Keep OKF `status` separate from `simo.work.state`.

## Delegate with bounded packets

A Task Brief grants only the reads and mutations explicitly listed. Include one measurable objective, in/out scope, locked decisions, inputs, dependencies, acceptance IDs, evidence required, stop conditions, and return contract.

A Result Packet stays compact and references artifacts rather than embedding logs or diffs. Record outcome, deliverables, bounded findings and confidence, changed paths, verification, knowledge-promotion candidates, work advancement, assumptions, unresolved items, and next action.

Only the integration owner applies repository changes. A knowledge owner promotes accepted durable results. Release the mutation lease before independent verification or verify an immutable revision.

## Close only on evidence

Before `done`:

1. Check every acceptance and execution item truthfully.
2. Link every claimed outcome to proportional evidence with explicit `proves` and `does_not_prove` boundaries.
3. Resolve or explicitly defer material decisions.
4. Add truthful verification to `plan.md` only after checking the bundle and claimed resources.
5. Promote durable results into normal concepts or ADRs; Work Plans never become canonical product or architecture authority.
6. Record a commit/PR reference or an explicit no-publication reason.
7. Run `$curate-simo-knowledge` validation, the knowledge regression suite, and relevant implementation checks.

Keep terminal plans at their original paths so OKF concept IDs remain stable. Remove them from active listings and link them from `docs/work/archive/index.md` when that index exists.

Return the work ID, state, next action, changed artifacts, evidence IDs, promoted concept IDs, verification performed, and remaining gates.
