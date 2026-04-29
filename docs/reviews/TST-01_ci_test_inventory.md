# TST-01 — CI / Test Surface Inventory

**Produced:** 2026-04-29  
**Branch:** claude/ci-test-consolidation-VV6y4  
**Purpose:** Complete enumeration of every workflow, script, and test in CI — mapped to canonical gate categories.

---

## Summary Counts

| Surface | Count |
|---|---|
| Workflow files | 17 |
| Pytest test files | 835 |
| TypeScript/Jest test files | 47 |
| Scripts used directly in CI | 28 |
| Total scripts in `scripts/` | ~240 |
| Contract schema files | 150+ |
| Governance artifacts | 10+ |

*Pytest collected test count is not feasible to run in isolation because many tests depend on fixtures and modules that require the full repo install. Estimated count based on file count and average test density (~8–12 tests per file): approximately 6,000–10,000 collected tests.*

---

## Workflow Files

### 1. `pr-pytest.yml` — Trigger: `pull_request` (all paths)
**Job:** `pytest`  
**Scripts called:**
- `scripts/build_preflight_pqx_wrapper.py`
- `scripts/run_contract_preflight.py`
- `scripts/run_github_pr_autofix_contract_preflight.py` (conditional on repair eligibility)

**Generated CI artifacts:**
- `outputs/contract_preflight/contract_preflight_result_artifact.json`
- `outputs/contract_preflight/pytest_execution_record.json`
- `outputs/contract_preflight/pytest_selection_integrity_result.json`
- `outputs/contract_preflight/contract_preflight_report.md`
- `outputs/contract_preflight/contract_preflight_diagnosis_bundle.md`

**Gate classification:** Contract Gate + Runtime Test Gate (combined — this is the god workflow)  
**Required check:** `PR / pytest` (canonical per `docs/governance/required_pr_checks.json`)  
**Notes:** This is the primary PR gate. It embeds test selection, schema enforcement, pytest execution, and trust validation inline. Contains ~160 lines of inline Python policy in the workflow YAML itself — this is the main duplication and complexity risk.

---

### 2. `artifact-boundary.yml` — Trigger: `push` (main, release/**, codex/**), `pull_request` (all paths)
**Jobs:**
- `enforce-artifact-boundary` → `scripts/check_artifact_boundary.py`
- `validate-module-architecture` → `scripts/validate_module_architecture.py`
- `validate-orchestration-boundaries` → `scripts/validate_orchestration_boundaries.py`
- `system-registry-guard` → `scripts/run_authority_shape_preflight.py`, `scripts/run_authority_drift_guard.py`, `scripts/run_system_registry_guard.py`, `scripts/run_authority_leak_guard.py`
- `governed-contract-preflight` (needs all 4 above) → `scripts/build_preflight_pqx_wrapper.py`, `scripts/run_contract_preflight.py`
- `run-pytest` (needs all 4 above) → `pytest` (bare, non-authoritative)

**Generated CI artifacts:**
- `outputs/system_registry_guard/system_registry_guard_result.json`
- `outputs/authority_leak_guard/authority_leak_guard_result.json`
- `outputs/authority_shape_preflight/authority_shape_preflight_result.json`
- `outputs/contract_preflight/contract_preflight_result_artifact.json`

**Gate classification:** Contract Gate + Runtime Test Gate  
**Notes:** Overlaps heavily with `pr-pytest.yml`. Both run `build_preflight_pqx_wrapper.py` + `run_contract_preflight.py` on PRs. The `run-pytest` job here is explicitly marked "Non-authoritative redundancy signal only." This is a known duplication surface.

---

### 3. `lifecycle-enforcement.yml` — Trigger: `push` (main, release/**, codex/**), `pull_request` (all paths)
**Jobs:**
- `validate-lifecycle-definitions` → `scripts/verify_environment.py`, `scripts/validate_lifecycle_data.py`
- `run-lifecycle-tests` → `pytest tests/test_lifecycle_enforcer.py`
- `eval-ci-gate` → `scripts/run_eval_ci_gate.py`
- `sel-replay-gate` → `scripts/run_sel_orchestration.py`, `scripts/run_sel_replay_gate.py`
- `governed-failure-injection-gate` → `scripts/run_governed_failure_injection.py`, `pytest tests/test_governed_failure_injection.py`

**Gate classification:** Runtime Test Gate + Certification Gate (SEL replay, eval CI)  
**Notes:** Mixes lifecycle validation, eval gating, and SEL replay in one workflow. These should be separated into canonical gates.

---

### 4. `strategy-compliance.yml` — Trigger: `pull_request` (paths: docs/roadmaps/**, docs/architecture/**, scripts/check_strategy_compliance.py, contracts/schemas/roadmap_output.schema.json)
**Jobs:**
- `strategy-compliance` → `scripts/check_strategy_compliance.py`

**Gate classification:** Governance Gate  
**Notes:** Narrow path trigger. Used by `pr-autofix-contract-preflight.yml` as its triggering workflow.

---

### 5. `pr-autofix-contract-preflight.yml` — Trigger: `workflow_run` (on strategy-compliance completed)
**Jobs:**
- `explicit-fork-skip` (fork safety guard)
- `governed-contract-preflight-autofix` → `scripts/build_preflight_pqx_wrapper.py`, `scripts/run_contract_preflight.py`, `scripts/run_github_pr_autofix_contract_preflight.py`

**Gate classification:** Contract Gate (repair path)  
**Notes:** Triggered only when strategy-compliance fails. Runs the same preflight scripts as `pr-pytest.yml` and `artifact-boundary.yml`. Third surface calling `run_contract_preflight.py`.

---

### 6. `3ls-registry-gate.yml` — Trigger: `pull_request` (paths: docs/architecture/system_registry.md, contracts/schemas/**, evals/eval_case_library.json, spectrum_systems/governance/**)
**Jobs:**
- `registry-compliance` → inline Python using `spectrum_systems/governance/registry_drift_validator.py`, `spectrum_systems/governance/contract_enforcer.py`

**Gate classification:** Governance Gate  
**Notes:** Schema coverage check (80% threshold, warn-only) + registry drift validator. Does not fail closed on eval coverage gaps.

---

### 7. `review-artifact-validation.yml` — Trigger: `push`/`pull_request` (paths: design-reviews/**, docs/reviews/**, scripts/check_review_registry.py, etc.)
**Jobs:**
- `validate-review-artifacts` → `scripts/run_review_artifact_validation.py`

**Gate classification:** Governance Gate  
**Notes:** Review artifact governance. Narrow path trigger.

---

### 8. `pr-autofix-review-artifact-validation.yml` — Trigger: (not read in detail; companion to review-artifact-validation)
**Gate classification:** Governance Gate (repair path)

---

### 9. `release-canary.yml` — Trigger: `push`/`pull_request` (paths: release-relevant files), `workflow_dispatch`
**Jobs:**
- `smoke-release-canary` → `scripts/run_release_canary.py`

**Gate classification:** Certification Gate  
**Notes:** Release comparison gate. Only fires on touched release-related paths.

---

### 10. `dashboard-deploy-gate.yml` — Trigger: `pull_request` (paths: dashboard/**, scripts/run_rq_master_01.py, etc.)
**Jobs:**
- `dashboard-gate` → `scripts/run_rq_master_01.py`, `scripts/refresh_dashboard.sh`, `scripts/validate_dashboard_public_artifacts.py`, `dashboard/npm lint + build`

**Gate classification:** Runtime Test Gate (Dashboard Deploy sub-gate)  
**Notes:** Floating — not connected to canonical gate model. No gate result artifact.

---

### 11. `ecosystem-registry-validation.yml` — Trigger: `push` (main), `pull_request` (paths: ecosystem/**, contracts/standards-manifest.json, etc.), `workflow_dispatch`
**Jobs:**
- `validate-ecosystem-registry` → `scripts/validate_ecosystem_registry.py`, `pytest tests/test_ecosystem_registry.py`

**Gate classification:** Governance Gate  
**Notes:** Narrow path trigger. Well-scoped.

---

### 12. `cross-repo-compliance.yml` — Trigger: `workflow_dispatch`, `schedule` (weekly Mondays), `push` (main, paths: governance/**, contracts/**, etc.)
**Jobs:**
- `governance-manifest-validation` → `python -m pytest` (full), `scripts/validate_governance_manifest.py`
- `cross-repo-compliance` → `governance/compliance-scans/run-cross-repo-compliance.js`
- `policy-engine` → `governance/policies/run-policy-engine.py`
- `dependency-graph` → `scripts/generate_dependency_graph.py`
- `contract-enforcement` → `scripts/run_contract_enforcement.py`
- `observability-reports` → `scripts/generate_ecosystem_health_report.py`, `scripts/generate_ecosystem_architecture_graph.py`

**Gate classification:** Governance Gate (nightly/weekly)  
**Notes:** Weekly/dispatch/main-push only — not a PR gate. Contains `python -m pytest` (full suite run). Should be classified as Nightly Deep Gate material.

---

### 13. `design-review-scan.yml` — Trigger: `push` (paths: design-reviews/*.md)
**Jobs:**
- `scan-review` → inline `grep` for Repository Actions

**Gate classification:** Governance Gate (informational only — no fail condition)  
**Notes:** No blocking condition. Informational scan.

---

### 14. `review_trigger_pipeline.yml` — Trigger: `pull_request_review`, `issue_comment`, `workflow_dispatch`
**Jobs:**
- `ingest-and-run-ril` → `python -m spectrum_systems.modules.runtime.github_review_ingestion`, `spectrum_systems.modules.runtime.github_pr_feedback`

**Gate classification:** Governance Gate (runtime review pipeline)  
**Notes:** Event-driven review ingestion. Not a test gate. Authority path for review-driven execution.

---

### 15. `closure_continuation_pipeline.yml` — Trigger: `workflow_run` (on review-trigger-pipeline), `workflow_dispatch`
**Jobs:**
- `closure-continuation` → `python -m spectrum_systems.modules.runtime.github_closure_continuation`, `spectrum_systems.modules.runtime.github_pr_feedback`

**Gate classification:** Governance Gate (runtime continuation pipeline)  
**Notes:** Continuation of review pipeline. Not a test gate.

---

### 16. `claude-review-ingest.yml` — (not fully read; handles Claude review ingestion)
**Gate classification:** Governance Gate (operational)

---

### 17. `ssos-project-automation.yml` — (not fully read; project automation)
**Gate classification:** Not a test gate — operational automation

---

## Scripts Directly Invoked by CI Workflows

| Script | Workflow(s) | Gate Classification |
|---|---|---|
| `scripts/build_preflight_pqx_wrapper.py` | pr-pytest, artifact-boundary, pr-autofix-contract-preflight | Contract Gate |
| `scripts/run_contract_preflight.py` | pr-pytest, artifact-boundary, pr-autofix-contract-preflight | Contract Gate |
| `scripts/run_github_pr_autofix_contract_preflight.py` | pr-pytest, pr-autofix-contract-preflight | Contract Gate (repair) |
| `scripts/check_artifact_boundary.py` | artifact-boundary | Contract Gate |
| `scripts/validate_module_architecture.py` | artifact-boundary | Contract Gate |
| `scripts/validate_orchestration_boundaries.py` | artifact-boundary | Contract Gate |
| `scripts/run_authority_shape_preflight.py` | artifact-boundary | Contract Gate |
| `scripts/run_authority_drift_guard.py` | artifact-boundary | Contract Gate |
| `scripts/run_system_registry_guard.py` | artifact-boundary | Contract Gate |
| `scripts/run_authority_leak_guard.py` | artifact-boundary | Contract Gate |
| `scripts/verify_environment.py` | lifecycle-enforcement | Runtime Test Gate |
| `scripts/validate_lifecycle_data.py` | lifecycle-enforcement | Runtime Test Gate |
| `scripts/run_eval_ci_gate.py` | lifecycle-enforcement | Certification Gate |
| `scripts/run_sel_orchestration.py` | lifecycle-enforcement | Certification Gate |
| `scripts/run_sel_replay_gate.py` | lifecycle-enforcement | Certification Gate |
| `scripts/run_governed_failure_injection.py` | lifecycle-enforcement | Certification Gate |
| `scripts/check_strategy_compliance.py` | strategy-compliance | Governance Gate |
| `scripts/run_review_artifact_validation.py` | review-artifact-validation | Governance Gate |
| `scripts/run_release_canary.py` | release-canary | Certification Gate |
| `scripts/run_rq_master_01.py` | dashboard-deploy-gate | Runtime Test Gate |
| `scripts/refresh_dashboard.sh` | dashboard-deploy-gate | Runtime Test Gate |
| `scripts/validate_dashboard_public_artifacts.py` | dashboard-deploy-gate | Runtime Test Gate |
| `scripts/validate_ecosystem_registry.py` | ecosystem-registry-validation | Governance Gate |
| `scripts/validate_governance_manifest.py` | cross-repo-compliance | Governance Gate |
| `scripts/run_contract_enforcement.py` | cross-repo-compliance | Governance Gate |
| `scripts/generate_dependency_graph.py` | cross-repo-compliance | Governance Gate |
| `scripts/generate_ecosystem_health_report.py` | cross-repo-compliance | Governance Gate |
| `scripts/generate_ecosystem_architecture_graph.py` | cross-repo-compliance | Governance Gate |

---

## Pytest Test Surfaces

835 Python test files located in `tests/`. Key clusters:

| Directory/Pattern | Approximate File Count | Gate Classification |
|---|---|---|
| `tests/test_aex_*.py` | ~12 | Contract Gate |
| `tests/test_contract_preflight*.py` | ~3 | Contract Gate |
| `tests/test_*schema*.py` / `tests/test_contracts.py` | ~8 | Contract Gate |
| `tests/test_system_registry*.py` | ~5 | Contract Gate |
| `tests/test_artifact_boundary*.py` | ~3 | Contract Gate |
| `tests/hop/test_*.py` | ~35 | Runtime Test Gate |
| `tests/test_eval_*.py` | ~25 | Certification Gate |
| `tests/test_*_certification*.py` | ~5 | Certification Gate |
| `tests/test_*governance*.py` | ~15 | Governance Gate |
| `tests/governance/test_*.py` | ~6 | Governance Gate |
| `tests/test_lifecycle_enforcer.py` | 1 | Runtime Test Gate |
| `tests/test_governed_failure_injection.py` | 1 | Certification Gate |
| `tests/metrics/test_met_*.py` | ~5 | Runtime Test Gate |
| `tests/aex/test_admission_replay.py` | 1 | Contract Gate |
| `tests/test_3ls_*.py` | ~15 | Runtime Test Gate / Governance Gate |
| Remaining (~700 files) | ~700 | Mixed — see TST-09 for full mapping |

---

## Jest / TypeScript Test Surfaces

47 TypeScript test files in `tests/`:

| Directory | Files | Gate Classification |
|---|---|---|
| `tests/artifact-store/` | 3 | Runtime Test Gate |
| `tests/e2e/` | 1 | Runtime Test Gate (nightly) |
| `tests/governance/` | 15 | Governance Gate |
| `tests/integration/` | 3 | Runtime Test Gate |
| `tests/mvp-1` through `tests/mvp-13/` | 13 | Runtime Test Gate |
| `tests/replay/` | 1 | Certification Gate |
| `tests/unit/` | 9 | Runtime Test Gate |

---

## Duplicated Enforcement Surfaces

1. **`run_contract_preflight.py` called in 3 places:** `pr-pytest.yml`, `artifact-boundary.yml` (`governed-contract-preflight` job), and `pr-autofix-contract-preflight.yml`. The trust validation inline Python in `pr-pytest.yml` and `pr-autofix-contract-preflight.yml` is ~160 lines duplicated nearly verbatim.

2. **Trust validation logic duplicated inline:** Both `pr-pytest.yml` and `pr-autofix-contract-preflight.yml` contain nearly identical inline Python blocks (~160 lines) that validate `pytest_execution_record`, `pytest_selection_integrity_result`, and provenance fields. This should be a single canonical gate runner.

3. **`artifact-boundary.yml` runs a non-authoritative `pytest`** at the end alongside an authoritative preflight — these two signals are mixed in one workflow without a canonical gate separation.

4. **`cross-repo-compliance.yml` runs `python -m pytest` (full suite)** on main/schedule. This is a deep gate mixed into a compliance workflow.

5. **`lifecycle-enforcement.yml` mixes** lifecycle validation, eval CI, SEL replay, and failure injection into one workflow. Each of these maps to a different canonical gate.

---

## Components Without Clear Gate Mapping

- `design-review-scan.yml`: Informational grep — no blocking condition, no artifact produced.
- `scripts/run_rq_master_01.py` in `dashboard-deploy-gate.yml`: Not connected to canonical gate model.
- `tests/metrics/test_met_*.py`: Mapped loosely via selection policy but no gate assignment in baseline.
- `pr-autofix-contract-preflight.yml` runs in response to `strategy-compliance` completion — the authority chain from strategy compliance → contract preflight autofix is not documented in canonical gate terms.
- `ssos-project-automation.yml`: Project automation, not test gating.
- `claude-review-ingest.yml`: Review operational tooling, not test gating.

---

## Canonical Gate Mapping Summary

| Workflow / Script | Contract Gate | Runtime Test Gate | Governance Gate | Certification Gate |
|---|:---:|:---:|:---:|:---:|
| pr-pytest.yml | ✓ (primary) | ✓ (pytest exec) | | |
| artifact-boundary.yml | ✓ | ✓ (redundant) | | |
| lifecycle-enforcement.yml | | ✓ | | ✓ |
| strategy-compliance.yml | | | ✓ | |
| pr-autofix-contract-preflight.yml | ✓ (repair) | | | |
| 3ls-registry-gate.yml | | | ✓ | |
| review-artifact-validation.yml | | | ✓ | |
| release-canary.yml | | | | ✓ |
| dashboard-deploy-gate.yml | | ✓ | | |
| ecosystem-registry-validation.yml | | | ✓ | |
| cross-repo-compliance.yml | | ✓ (deep) | ✓ | |
| design-review-scan.yml | | | ✓ (info) | |
| review_trigger_pipeline.yml | | | ✓ (operational) | |
| closure_continuation_pipeline.yml | | | ✓ (operational) | |
