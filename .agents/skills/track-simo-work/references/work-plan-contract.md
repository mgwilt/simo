# Simo Work Plan contract

## Bundle route

Create only artifacts the work needs. The core bundle is:

```text
docs/work/W-YYYYMMDD-slug/
  index.md
  plan.md
  scope.md
  acceptance.md
  execution.md
  checkpoint.md
  decisions.md
  verification.md
  closure.md
  evidence/
    index.md
    E-NNN-slug.md
  tasks/            # only for delegated work
    index.md
    T-NNN.md
  results/          # only for delegated work
    index.md
    R-NNN.md
```

`index.md` is a short route and has no frontmatter. Every other Markdown file is an OKF concept and follows `$curate-simo-knowledge`.

## Plan owner

`plan.md` alone owns shared lifecycle metadata:

```yaml
simo:
  profile_version: 1
  stable_id: W-YYYYMMDD-slug
  authority: coordination
  repository_paths: [<affected-path>]
  owner: <truthful-actor-or-unassigned>
  work:
    schema_version: 1
    id: W-YYYYMMDD-slug
    state: proposed
    mode: read_only # or mutation
    priority: p1
    accountable: <truthful-actor-or-unassigned>
    created_at: <ISO-8601-datetime>
    updated_at: <ISO-8601-datetime>
    depends_on: []
    knowledge_refs: []
    write_paths: []
    next_action: <one bounded action>
    blocker: null
```

Work parts keep only their own stable ID, authority, repository paths, owner, and a `simo.work.parent_id` reference. Do not repeat the full plan mapping in every part.

## Part ownership

- `scope.md`: included work, exclusions, authorization and external-effect boundary.
- `acceptance.md`: measurable `A-NNN` items and required evidence level.
- `execution.md`: bounded `T-NNN` items, dependencies, owner, and state.
- `checkpoint.md`: current revision, dirty paths, completed state, blocker, next action, and references required to resume. Replace; do not append.
- `decisions.md`: work-local `D-NNN` choices, rationale, alternatives, consequences, and promotion target.
- `verification.md`: exact checks, revision/environment, pass/fail/not-run, and evidence references.
- `closure.md`: actual outcome, unresolved scope, promoted knowledge, and commit/PR or explicit no-publication reason.
- `evidence/E-NNN-slug.md`: one bounded claim and its proof limits.

## Task Brief

Use one `Task Brief` concept per delegated task with:

- work ID and `T-NNN` task ID;
- one measurable objective and context digest;
- `scope_in`, `scope_out`, and locked decisions;
- exact input refs and governing knowledge refs;
- read authority, mutation mode, allowed paths, and external effects;
- dependencies, acceptance IDs, evidence required, stop conditions;
- return contract `Result Packet`.

For a mutation lease, add lease ID, holder task ID, base revision/reported state, allowed paths, commit/publication authorization, and release condition. Intended plan paths alone are not a lease.

## Result Packet

Use one `Result Packet` concept per delegated result with:

- task ID and outcome (`complete`, `partial`, `blocked`, `failed`);
- summary and artifact references;
- bounded findings with severity, confidence, and evidence refs;
- changed files, generated assets, and commits;
- verification check/result/evidence;
- knowledge updates applied or proposed;
- acceptance/task IDs advanced, current checkpoint, and next action;
- assumptions, unresolved items, and recommended follow-ups.

Keep the packet compact. Store raw logs and full diffs elsewhere and reference them.

## Evidence Record

Each Evidence Record contains:

- work and evidence IDs;
- source revision plus relevant dirty paths;
- exact claim being tested;
- method, command, editor/runtime operation, or inspection;
- result and artifact/hash references;
- `proves`, `does_not_prove`, freshness, and verifier.

Never infer runtime, latency, deterministic replay, deployment, security, or user-visible behavior from documentation presence or structural validation.

## Lifecycle gates

- `ready`: scope, exclusions, acceptance, owners, decisions, and dependencies are sufficient to execute.
- `active`: dependencies are done and no active mutation path overlaps.
- `review`: execution is complete enough for independent review and the mutation lease is released or the revision is immutable.
- `done`: acceptance and execution are truthful; claimed outcomes have evidence; decisions are resolved/deferred; verification is truthful; durable knowledge is promoted; publication reference or no-publication reason exists.
- `blocked`: reason, attempts, required input/state, owner, and next action exist.
- `cancelled`: reason and preserved useful results exist.

Terminal plans remain at their original path. Archive indexes classify them without moving them.
