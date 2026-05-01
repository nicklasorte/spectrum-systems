# PAR-CI-01 — Fix Actions

This document records the must-fix findings raised in
`docs/reviews/PAR-CI-01_redteam.md` and the resolution applied in this
PR.

PAR-CI-01 is observation-only; this document records remediation
evidence. It does not redefine ownership and does not issue any
admission_signal, certification_signal, promotion_signal,
enforcement_signal, or final-gate signal — those remain with the
canonical owners declared in `docs/architecture/system_registry.md`.

## Must-fix findings (resolved in this PR)

### F1. CI must use the same shard runner as APR

**Resolution:** `.github/workflows/pr-pytest.yml` matrix job
`pr-test-shards` invokes `scripts/run_pr_test_shards.py` — the same
canonical PAR-BATCH-01 runner used by APR
(`scripts/run_agent_pr_precheck.py::evl_pr_test_shards`).

Parity tests added:
- `test_pr_pytest_workflow_uses_canonical_shard_runner`
- `test_apr_uses_canonical_shard_runner`
- `test_pr_pytest_workflow_does_not_introduce_duplicate_selector`

### F2. Aggregator must fail closed on fail / missing / unknown

**Resolution:** `pr-test-shards-aggregate` inspects every per-shard
artifact, validates the canonical schema, and records
`shard_status_fail`, `shard_status_missing`, `shard_status_unknown`,
`shard_artifact_missing`, `shard_artifact_unreadable`, or
`shard_artifact_invalid` blocking reasons. Any non-empty blocking
reason flips `overall_status = block` and exits the aggregator
non-zero.

Parity test added:
- `test_pr_pytest_workflow_aggregator_validates_shard_artifacts`

### F3. Matrix shard list must equal canonical set

**Resolution:** matrix lists exactly the six canonical shards
(`contract`, `governance`, `runtime_core`, `changed_scope`,
`generated_artifacts`, `measurement`). The legacy `dashboard` shard
name is absent.

Parity tests added:
- `test_pr_pytest_workflow_matrix_lists_canonical_shards`
- `test_pr_pytest_workflow_matrix_matches_runner_canonical_shards`
- `test_pr_pytest_workflow_matrix_matches_schema_canonical_shards`

### F4. No monolithic pytest inside the shard matrix

**Resolution:** the matrix job invokes only
`scripts/run_pr_test_shards.py`. No direct `python -m pytest` call is
present in the matrix slice.

Parity test added:
- `test_pr_pytest_workflow_does_not_run_monolithic_shard_pytest`

### F5. Per-shard artifact upload required

**Resolution:** each matrix entry uploads
`outputs/pr_test_shards/${{ matrix.shard }}.json` and
`outputs/pr_test_shards/pr_test_shards_summary.json` via
`actions/upload-artifact@v4`.

Parity test added:
- `test_pr_pytest_workflow_uploads_per_shard_artifact`

### F6. Authority-safe vocabulary

**Resolution:** workflow labels and comments use only authority-safe
terms (`shard_status`, `readiness observation`, `measurement
observation`, `artifact-backed evidence`, `finding`, `policy
observation`). The new shard / aggregator surface contains no bare
reserved-authority substrings from the
approval_signal / certification_signal / promotion_signal /
enforcement_signal / decision_signal / authorization_signal /
verdict_signal clusters; the canonical list is pinned by the parity
test below (the bare-token list lives in the parity test source,
which is excluded from the authority-shape preflight scan scope).

Parity test added:
- `test_pr_pytest_workflow_aggregator_uses_authority_safe_vocabulary`

### F7. CI drift detector must accept canonical runner

**Resolution:** `scripts/run_ci_drift_detector.py`'s
`_check_workflow_bypasses_canonical_selector` now accepts either
`scripts/run_pr_test_shards.py` (canonical PAR-BATCH-01) or
`scripts/select_pr_test_shard.py` (legacy) as evidence that the
workflow uses a canonical selector wrapper.

### F8. Required-test mapping for `.github/workflows/pr-pytest.yml`

**Resolution:** added an entry in
`spectrum_systems/modules/runtime/pr_test_selection.py::_REQUIRED_SURFACE_TEST_OVERRIDES`,
`docs/governance/preflight_required_surface_test_overrides.json`, and
`docs/governance/pytest_pr_selection_integrity_policy.json` mapping
`.github/workflows/pr-pytest.yml` to:

- `tests/test_artifact_boundary_workflow_pytest_policy_observation.py`
- `tests/test_agent_pr_precheck_workflow_parity.py`
- `tests/test_pr_test_shards.py`

This prevents `MISSING_REQUIRED_SURFACE_MAPPING` for future changes to
`pr-pytest.yml` and binds the workflow to the matrix parity tests.

## Out-of-scope (deferred to a later slice)

- Retirement of `scripts/select_pr_test_shard.py`,
  `scripts/run_pr_gate.py`, and `tests/test_pr_gate_parallel.py`. CI
  no longer invokes them; unit-test coverage and PAR-BATCH-01
  selector audit decide retirement timing.
- Any changes to APR / CLP / APU behavior beyond preserving parity
  with the canonical shard runner.
- Dashboard / token / PRL / FRE expansions.
