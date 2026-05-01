# PAR-CI-01 — Red-team Review

PAR-CI-01 wires the canonical PAR-BATCH-01 PR test shard runner
(`scripts/run_pr_test_shards.py`) into a GitHub Actions matrix so that
PR shard tests run in parallel using the same selector path APR uses.

This document is a measurement observation. It does not redefine
ownership, issue admission, or claim final-gate signal. Canonical
ownership remains with the systems declared in
`docs/architecture/system_registry.md`.

## Surface

- `.github/workflows/pr-pytest.yml`
  - matrix job `pr-test-shards` (one entry per canonical shard)
  - aggregator job `pr-test-shards-aggregate`
  - unchanged `pytest` job (governed contract preflight)
- `scripts/run_ci_drift_detector.py` — workflow-bypass check now
  accepts either the canonical `run_pr_test_shards.py` runner or the
  legacy `select_pr_test_shard.py` wrapper.
- `tests/test_agent_pr_precheck_workflow_parity.py` — extended with
  PAR-CI-01 matrix parity assertions.
- `spectrum_systems/modules/runtime/pr_test_selection.py` and
  `docs/governance/preflight_required_surface_test_overrides.json` and
  `docs/governance/pytest_pr_selection_integrity_policy.json` — added
  required-test mapping for `.github/workflows/pr-pytest.yml`.

## Threat model

PAR-CI-01 is observation-only. The risk surfaces are:

1. CI shard signal silently diverges from APR.
2. Workflow appears to pass while a shard fails.
3. Workflow appears to pass while a shard artifact is missing or stale.
4. Skipped shards mask real failures.
5. Matrix shard list drifts away from schema / runner / tests.
6. Reserved authority terms leak into workflow labels or comments.
7. CI executes a duplicate selector path or a monolithic pytest pass
   that bypasses canonical shard selection.

## Red-team findings

### R1. GitHub matrix uses a different selector than APR

**Risk:** historical regression mode. Earlier CI invoked
`scripts/select_pr_test_shard.py`; APR invokes
`scripts/run_pr_test_shards.py`. Two different wrappers can drift.

**Mitigation:**
- The new matrix invokes only `scripts/run_pr_test_shards.py` — the
  same canonical runner APR uses.
- Parity test
  `test_pr_pytest_workflow_uses_canonical_shard_runner` and
  `test_apr_uses_canonical_shard_runner` assert this.
- Parity test
  `test_pr_pytest_workflow_does_not_introduce_duplicate_selector`
  asserts the legacy `select_pr_test_shard.py` is not referenced
  inside `pr-pytest.yml`.

**Status:** mitigated.

### R2. One shard fails but aggregate passes

**Risk:** the aggregator could be permissive about shard `fail` /
`missing` / `unknown` and report `pass`.

**Mitigation:**
- Per-shard runner exit code is fail-closed: each matrix job invokes
  `run_pr_test_shards.py` with `--required-shards <matrix.shard>`,
  so a `fail` / `missing` / `unknown` exits the runner non-zero and
  the matrix job fails.
- Aggregator inspects every per-shard `pr_test_shard_result` artifact,
  validates it against the canonical schema, and records a blocking
  reason for any `fail` / `missing` / `unknown` status.
- Aggregator also inspects `needs.pr-test-shards.result` and records
  a blocking reason when the upstream matrix did not conclude
  `success` (e.g., `cancelled`, runner crash).
- Parity test
  `test_pr_pytest_workflow_aggregator_validates_shard_artifacts`
  pins the blocking-reason vocabulary in the workflow.

**Status:** mitigated.

### R3. Missing shard artifact treated as clean

**Risk:** if a matrix job uploads no per-shard artifact (job crash,
upload failure), aggregator could silently skip that shard and report
`pass`.

**Mitigation:**
- Aggregator iterates the canonical shard list and records
  `<shard>:shard_artifact_missing` for every shard whose
  `outputs/pr_test_shards/<shard>.json` is absent.
- Any non-empty `blocking_reasons` flips `overall_status = block` and
  exits the aggregator non-zero.
- Parity test
  `test_pr_pytest_workflow_aggregator_validates_shard_artifacts`
  pins the `shard_artifact_missing` reason code.

**Status:** mitigated.

### R4. Stale shard artifact reused

**Risk:** an older `outputs/pr_test_shards/<shard>.json` from a prior
job could be carried forward and trusted.

**Mitigation:**
- Each matrix job runs in a fresh GitHub Actions runner — there is no
  pre-existing `outputs/pr_test_shards/` directory.
- The aggregator downloads artifacts only via
  `actions/download-artifact` from the current workflow run with the
  pattern `pr-test-shard-*`.
- The canonical runner overwrites `<shard>.json` per invocation; the
  matrix entry only writes the shard it owns, so cross-shard staleness
  inside a single job is impossible by construction.
- APR's `evl_pr_test_shards` already enforces the broader
  stale-summary fail-closed guard
  (`pr_test_shard_summary_stale_or_untrusted`), preserving APR/CI
  parity.

**Status:** mitigated.

### R5. Skipped shard treated as clean without policy

**Risk:** a `skipped` shard could mask a missed signal if no policy
covers it.

**Mitigation:**
- Current canonical policy: `_build_summary` in
  `scripts/run_pr_test_shards.py` does not block on `skipped`. PAR-CI-01
  preserves this — `skipped` is treated as clean by the aggregator.
- The runner produces `skipped` only when the canonical selector
  returns `empty_allowed` (no governed surface change for that shard
  or no test routed to that shard). This is the documented
  PAR-BATCH-01 behavior; no shard-semantics change here.
- Reason code on a `skipped` artifact (`empty_allowed_by_selector` or
  `no_tests_selected_for_shard`) is preserved for downstream replay.

**Status:** mitigated. Policy preserved; no new exception introduced.

### R6. Matrix shard list differs from schema / test canonical list

**Risk:** the workflow YAML drifts from
`scripts.run_pr_test_shards.CANONICAL_SHARDS` or from the schema enum.

**Mitigation:**
- Parity tests pin three sources to the same canonical set:
  - `test_pr_pytest_workflow_matrix_lists_canonical_shards` —
    workflow YAML
  - `test_pr_pytest_workflow_matrix_matches_runner_canonical_shards` —
    runner module
  - `test_pr_pytest_workflow_matrix_matches_schema_canonical_shards` —
    schema enum
- Adding or removing a shard requires a coordinated change to the
  workflow, the runner, the schema, and the parity test.

**Status:** mitigated.

### R7. Workflow runs monolithic pytest in addition to shards by accident

**Risk:** a future patch might add a step inside the matrix that
calls `python -m pytest ...` directly, silently bypassing the
canonical selector.

**Mitigation:**
- Parity test
  `test_pr_pytest_workflow_does_not_run_monolithic_shard_pytest`
  asserts the `pr-test-shards` matrix slice contains no
  `python -m pytest` invocation. The unchanged `pytest:` job (the
  governed contract preflight) is not part of this slice.

**Status:** mitigated.

### R8. APR and GitHub shard commands drift

**Risk:** APR invokes `run_pr_test_shards.py` with one argument shape;
the matrix invokes it with another, producing inconsistent shard
artifacts.

**Mitigation:**
- Both APR and the matrix invoke `scripts/run_pr_test_shards.py` with
  `--base-ref`, `--head-ref`, `--output-dir outputs/pr_test_shards`.
- The matrix additionally pins `--shards <matrix.shard>` and
  `--required-shards <matrix.shard>`. APR runs the full canonical set
  with the runner's `DEFAULT_REQUIRED_SHARDS`. The per-shard artifact
  shape is identical in both cases — this is a runner contract, not
  a CLI quirk.
- Parity test `test_apr_uses_canonical_shard_runner` and
  `test_pr_pytest_workflow_uses_canonical_shard_runner` both pin
  the runner script path.

**Status:** mitigated.

### R9. Artifact upload missing for shard result

**Risk:** a matrix entry runs but does not upload its per-shard
`pr_test_shard_result` artifact, breaking the aggregator.

**Mitigation:**
- Each matrix entry has an explicit
  `actions/upload-artifact@v4` step (`if: always()`) that uploads
  `outputs/pr_test_shards/${{ matrix.shard }}.json` and
  `outputs/pr_test_shards/pr_test_shards_summary.json`.
- Parity test
  `test_pr_pytest_workflow_uploads_per_shard_artifact` pins the
  upload path.
- `if-no-files-found: warn` is preserved on upload to surface the
  missing-upload condition without masking the matrix-level failure.

**Status:** mitigated.

### R10. Reserved authority terms in workflow / test labels

**Risk:** a label or comment in the new workflow surface uses a bare
reserved-authority substring (the
approval_signal / certification_signal / promotion_signal /
enforcement_signal / decision_signal / authorization_signal /
verdict_signal cluster terms) and silently leaks an authority claim.

**Mitigation:**
- Workflow surface uses authority-safe vocabulary:
  - `pr-test-shards` (matrix job)
  - `pr-test-shards-aggregate` (aggregator)
  - `shard_status_*` blocking reason codes
  - `readiness observation`, `measurement observation`,
    `artifact-backed evidence` in comments
- Parity test
  `test_pr_pytest_workflow_aggregator_uses_authority_safe_vocabulary`
  scans the new shard surface and asserts none of the reserved
  substrings are present.

**Status:** mitigated.

## Residual risks

- The existing `pytest:` job (governed contract preflight) inside
  `pr-pytest.yml` is unchanged and continues to execute selected
  pytest targets via the canonical preflight gate. PAR-CI-01 does
  not alter that surface; any drift between the shard matrix and
  the preflight-driven pytest is governed by APR / CLP / APU and
  is out of PAR-CI-01 scope.
- Legacy `scripts/select_pr_test_shard.py`, `scripts/run_pr_gate.py`,
  and `tests/test_pr_gate_parallel.py` remain in the repo and are
  unit-tested directly. CI no longer invokes them. This is intentional
  per PAR-CI-01 scope — selector retirement, if any, belongs to a
  later slice.
