# Governed PR Autofix Path — `review-artifact-validation`

## Purpose
Define a governed, fail-closed repo-mutation path for failed pull request runs of `review-artifact-validation`.

This path is **not** a bot feature. It is a governed repository-mutation path with explicit ownership boundaries and artifact lineage.

## Prompt type
WIRE

## Target trigger
- Workflow: `review-artifact-validation`
- Event transport: `workflow_run`
- Trigger condition: completed run with conclusion `failure`
- PR scope: same-repository PRs only (fork PRs are blocked)

## Two-layer model

### Layer 1 — GitHub Actions (transport only)
Workflow: `.github/workflows/pr-autofix-review-artifact-validation.yml`

Responsibilities:
1. Detect failed `review-artifact-validation` run for PR event.
2. Emit explicit fork-PR skip signal outside trusted mutation boundary.
2. Retrieve run logs and persist `.autofix/input/*` artifacts.
3. Invoke repo-native governed entrypoint.
4. Publish PR comment from emitted governed summary.

Prohibited in Layer 1:
- direct repair execution authority
- policy adjudication
- orchestration ownership
- closure authority

### Layer 2 — Repo-native governed path
Entrypoint: `python -m spectrum_systems.modules.runtime.github_pr_autofix_review_artifact_validation`

Responsibilities are explicitly partitioned by System Registry ownership.

## Ownership mapping (canonical)

### AEX — admission boundary (entry only)
- Builds and validates admission artifacts for repo mutation:
  - `build_admission_record`
  - `normalized_execution_request`
- Rejects invalid/malformed repo-write requests fail closed.

### TLC — orchestration lineage
- Emits `tlc_handoff_record` referencing admitted AEX artifacts.
- Declares intended path `TLC -> TPA -> PQX`.

### TPA — trust/policy admissibility
- Emits `tpa_slice_artifact` (phase `gate`) as governed scope/policy gate.
- Confirms bounded admissibility before execution path continues.

### PQX — execution owner
- Owns repair execution and validation replay execution.
- In this slice, only deterministic bounded text-repair actions are allowed.
- A commit is created only after replay validation passes.
- Push is attempted only when a non-`GITHUB_TOKEN` mutation token is present.

### RIL + FRE + RQX boundaries
- RIL interprets workflow log failures into structured signal artifacts.
- FRE creates bounded repair-plan artifacts.
- RQX remains review-loop execution authority only and is not bypassed.

### SEL — fail-closed enforcement
- Enforces required entry invariant artifacts.
- Blocks when repair plan is unsafe/empty.
- Blocks push when validation replay is missing, ambiguous, or failed.

### CDE + PRG boundaries
- CDE remains closure/readiness authority.
- PRG remains program governance authority.
- Neither authority is duplicated in this autofix transport/execution slice.

## Entry invariant
All repo-mutating work must include:
1. `build_admission_record` (AEX)
2. `normalized_execution_request` (AEX)
3. `tlc_handoff_record` (TLC)
4. `tpa_slice_artifact` (TPA)

Missing any required artifact is a fail-closed condition.

## Mandatory pre-push validation replay gate
Before push is allowed for autofix commits, repo-native execution must run replay checks equivalent to `review-artifact-validation`:
1. Node dependency install for artifact validator
2. `node scripts/validate-review-artifacts.js`
3. Python dependency setup
4. `python scripts/check_review_registry.py --fail-on-overdue`
5. `pytest` (narrowed scope only when safe determinism is available; otherwise full suite)

Replay output is emitted as `validation_result_record`.

SEL enforcement:
- any replay failure -> block push
- missing replay artifact -> block push
- ambiguous replay artifact -> block push

## Security model
1. Secrets boundary:
   - `OPENAI_API_KEY` for model access (if later repair planning needs it).
   - Preferred push identity: GitHub App token (`GITHUB_APP_TOKEN`).
   - Fallback push identity: `AUTOFIX_PUSH_TOKEN`.
2. Push token rule:
   - `GITHUB_TOKEN` is not relied on for mutation flows requiring rerun-trigger semantics.
   - `actions/checkout` disables persisted credentials; push auth is explicit in repo-native execution.
3. Fork boundary:
   - Fork PR workflow runs are blocked fail closed.
4. Secret exposure:
   - No untrusted branch execution path receives mutation-capable token by default.

## Fail-closed matrix
The path blocks when any of the following occurs:
- no PR is associated with run
- PR originates from fork repository
- workflow logs unavailable or empty
- AEX admission fails
- TLC lineage artifact missing/invalid
- TPA gate artifact missing/invalid
- no bounded safe repair is available
- bounded repair action target is missing or mismatched
- bounded repair applies but no git diff exists
- staged mutation set is empty
- replay validation missing
- replay validation ambiguous
- replay validation fails
- push token missing when push is requested

## Operability notes
- Current implementation intentionally prefers safety: it produces governed artifacts and blocks when no deterministic safe repair action can be proven.
- This preserves artifact-first execution and prevents shadow mutation paths.
