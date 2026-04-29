# CI Gate Model — Canonical Four-Gate Architecture

**Produced:** 2026-04-29  
**Branch:** claude/ci-test-consolidation-VV6y4  
**Version:** 1.0.0

---

## Overview

All CI trust enforcement in this repository flows through exactly four canonical gates. Every workflow, script, and test maps to one of these gates. No test or check may exist outside a gate without an explicit documented exception.

```
PR commit → Contract Gate → Test Selection Gate → Runtime Test Gate → Governance Gate
                                                          ↓
                                              (nightly/release only)
                                              Certification Gate
```

The PR gate orchestrator (`scripts/run_pr_gate.py`) calls the first four gates in order for every PR. The Certification Gate runs in full during nightly and release passes; a fast certification smoke check runs on every PR when certification-relevant paths are touched.

---

## Gate 1 — Contract Gate

### Purpose
Enforce schema validity, artifact boundary integrity, module architecture rules, system registry guard, and authority shape compliance before any test execution. This gate answers: "Is the PR structurally admissible?"

### Inputs
- Changed file paths (base SHA → head SHA)
- `contracts/schemas/` — schema definitions
- `docs/architecture/system_registry.md` — canonical system ownership
- `docs/governance/preflight_required_surface_test_overrides.json` — surface overrides
- `artifacts/pqx_runs/preflight.pqx_slice_execution_record.json` — authority evidence ref

### Outputs
- `outputs/contract_preflight/contract_preflight_result_artifact.json`
- `outputs/contract_preflight/pytest_execution_record.json`
- `outputs/contract_preflight/pytest_selection_integrity_result.json`
- `outputs/contract_preflight/contract_preflight_report.md`
- `outputs/contract_preflight/system_registry_guard_result.json`
- `outputs/authority_shape_preflight/authority_shape_preflight_result.json`
- `outputs/authority_drift_guard/authority_drift_guard_result.json`
- `outputs/authority_leak_guard/authority_leak_guard_result.json`
- Gate result: `outputs/gates/contract_gate_result.json`

### Artifact Schema
`contracts/schemas/contract_gate_result.schema.json`

### Fail-Closed Conditions
- Missing `contract_preflight_result_artifact.json` → BLOCK
- `strategy_gate_decision` == BLOCK → BLOCK
- `strategy_gate_decision` == WARN → BLOCK (WARN is not pass-equivalent on PR)
- Missing `pytest_execution_record_ref` → BLOCK
- Missing or non-canonical `pytest_execution_record` artifact → BLOCK
- `executed == false` in record → BLOCK
- Empty `selected_targets` → BLOCK
- Missing provenance fields in execution record → BLOCK
- Missing or non-canonical `pytest_selection_integrity_result` → BLOCK
- `selection_integrity_decision` != ALLOW when gate decision is ALLOW → BLOCK
- Module architecture violations → BLOCK
- Artifact boundary violations → BLOCK
- System registry authority violations → BLOCK (hard violations)

### Mapped Workflows / Scripts
- `pr-pytest.yml` (primary)
- `artifact-boundary.yml` (jobs: enforce-artifact-boundary, validate-module-architecture, validate-orchestration-boundaries, system-registry-guard, governed-contract-preflight)
- `pr-autofix-contract-preflight.yml` (repair path)
- `scripts/build_preflight_pqx_wrapper.py`
- `scripts/run_contract_preflight.py`
- `scripts/run_github_pr_autofix_contract_preflight.py`
- `scripts/check_artifact_boundary.py`
- `scripts/validate_module_architecture.py`
- `scripts/validate_orchestration_boundaries.py`
- `scripts/run_authority_shape_preflight.py`
- `scripts/run_authority_drift_guard.py`
- `scripts/run_system_registry_guard.py`
- `scripts/run_authority_leak_guard.py`
- Gate runner: `scripts/run_contract_gate.py`

### Invariants Protected
- No schema-invalid artifacts may be promoted
- No module may cross-write another module's artifact types
- No authority shape violations may reach main
- No orphaned governed surfaces without registry mapping
- Pytest execution must be owned by preflight — no shadow execution paths

### Pass Example
```json
{
  "gate_name": "contract_gate",
  "status": "allow",
  "strategy_gate_decision": "ALLOW",
  "pytest_execution_count": 47,
  "selected_targets": ["tests/test_contracts.py", "tests/test_aex_admission.py"],
  "selection_integrity_decision": "ALLOW"
}
```

### Fail Example
```json
{
  "gate_name": "contract_gate",
  "status": "block",
  "failure_summary": {
    "gate_name": "contract_gate",
    "failure_class": "trust_mismatch",
    "root_cause": "pytest_execution_record.executed == false",
    "blocking_reason": "PR allow with executed=false",
    "next_action": "Verify run_contract_preflight.py completed successfully",
    "affected_files": ["scripts/run_contract_preflight.py"],
    "failed_command": "scripts/run_contract_preflight.py",
    "artifact_refs": ["outputs/contract_preflight/pytest_execution_record.json"]
  }
}
```

---

## Gate 2 — Test Selection Gate

### Purpose
Validate that the set of tests selected for this PR is non-empty, properly derived from the changed paths, and passes integrity checks. This gate answers: "Is the selected test set trustworthy?"

### Inputs
- Changed file paths (base SHA → head SHA)
- `docs/governance/pytest_pr_selection_integrity_policy.json` — selection rules
- `docs/governance/pytest_pr_inventory_baseline.json` — fallback smoke baseline
- `outputs/contract_preflight/pytest_execution_record.json` — upstream selection record

### Outputs
- `outputs/gates/test_selection_gate_result.json`
- Selected test targets (artifact field)
- Fallback decision (whether smoke baseline was invoked)

### Artifact Schema
`contracts/schemas/test_selection_gate_result.schema.json`

### Fail-Closed Conditions
- Empty selected targets AND no fallback → BLOCK
- Selected targets not recorded in artifact → BLOCK
- Selection integrity decision != ALLOW → BLOCK
- Provenance fields missing from selection result → BLOCK
- Selection record hash mismatch with execution record → BLOCK
- Commit SHA mismatch between selection and execution records → BLOCK
- Governed surface touched but zero tests selected for that surface → BLOCK (unless explicit override)

### Mapped Workflows / Scripts
- Logic currently embedded in `scripts/run_contract_preflight.py`
- Gate runner: `scripts/run_test_selection_gate.py` (new)
- Policy: `docs/governance/pytest_pr_selection_integrity_policy.json`
- Fallback baseline: `docs/governance/pytest_pr_inventory_baseline.json`

### Invariants Protected
- Empty selection is never pass-equivalent
- Governed surface changes always trigger at least a smoke test
- Selection provenance is always hashed and traceable
- Selection cannot be fabricated or replayed from stale state

### Pass Example
```json
{
  "gate_name": "test_selection_gate",
  "status": "allow",
  "selection_integrity_decision": "ALLOW",
  "selected_targets": ["tests/test_aex_admission.py", "tests/test_contracts.py"],
  "fallback_invoked": false,
  "target_count": 2
}
```

### Fail Example
```json
{
  "gate_name": "test_selection_gate",
  "status": "block",
  "failure_summary": {
    "gate_name": "test_selection_gate",
    "failure_class": "empty_selection",
    "root_cause": "No tests selected for governed surface change in contracts/",
    "blocking_reason": "Governed surface touched with zero selected targets",
    "next_action": "Add test mapping for contracts/ in pytest_pr_selection_integrity_policy.json",
    "affected_files": ["contracts/schemas/new_schema.schema.json"],
    "failed_command": "scripts/run_test_selection_gate.py",
    "artifact_refs": ["outputs/gates/test_selection_gate_result.json"]
  }
}
```

---

## Gate 3 — Runtime Test Gate

### Purpose
Execute the selected tests (pytest + Jest where applicable) and verify all pass. This gate answers: "Do the tests pass?"

### Inputs
- Selected test targets from Test Selection Gate
- `outputs/contract_preflight/pytest_execution_record.json`
- Test runner configuration (pytest.ini / jest.config.js)

### Outputs
- `outputs/gates/runtime_test_gate_result.json`
- Test execution summary (pass/fail counts, duration)
- Failed test list

### Artifact Schema
`contracts/schemas/runtime_test_gate_result.schema.json`

### Fail-Closed Conditions
- Any selected test fails → BLOCK
- Pytest process exit code != 0 → BLOCK
- Execution count < minimum_selection_threshold → BLOCK
- `executed == false` → BLOCK
- No test output produced → BLOCK
- Missing provenance fields → BLOCK

### Mapped Workflows / Scripts
- `pr-pytest.yml` (pytest execution step)
- `artifact-boundary.yml` (`run-pytest` job — redundant, to be consolidated)
- `lifecycle-enforcement.yml` (`run-lifecycle-tests` job, `governed-failure-injection-gate` job)
- `ecosystem-registry-validation.yml` (pytest tests/test_ecosystem_registry.py)
- `dashboard-deploy-gate.yml` (dashboard lint + build)
- Gate runner: `scripts/run_runtime_test_gate.py` (new)

### Invariants Protected
- No PR may be promoted if any selected test fails
- Test execution is always recorded with provenance
- Jest and pytest results both feed into gate decision
- Runtime failures produce structured artifacts

### Pass Example
```json
{
  "gate_name": "runtime_test_gate",
  "status": "allow",
  "executed": true,
  "total_tests": 47,
  "passed": 47,
  "failed": 0,
  "duration_seconds": 12.4
}
```

### Fail Example
```json
{
  "gate_name": "runtime_test_gate",
  "status": "block",
  "failure_summary": {
    "gate_name": "runtime_test_gate",
    "failure_class": "test_failure",
    "root_cause": "tests/test_aex_admission.py::test_schema_validation FAILED",
    "blocking_reason": "1 test(s) failed",
    "next_action": "Fix failing test or fix the code under test",
    "affected_files": ["spectrum_systems/modules/aex/admission.py"],
    "failed_command": "python -m pytest tests/test_aex_admission.py",
    "artifact_refs": ["outputs/gates/runtime_test_gate_result.json"]
  }
}
```

---

## Gate 4 — Governance Gate

### Purpose
Validate that all governance artifacts, strategy compliance documents, schema registries, and ecosystem registries are consistent. This gate answers: "Is the PR governance-complete?"

### Inputs
- Changed files in: `docs/governance/`, `docs/architecture/`, `contracts/`, `spectrum_systems/governance/`
- `docs/architecture/system_registry.md`
- `evals/eval_case_library.json`
- Governance manifest: `docs/governance/governance_manifest.json`

### Outputs
- `outputs/gates/governance_gate_result.json`
- Strategy compliance result
- Registry drift report
- Ecosystem validation report

### Artifact Schema
`contracts/schemas/governance_gate_result.schema.json`

### Fail-Closed Conditions
- Strategy compliance violations on touched paths → BLOCK
- System registry missing required schema contract → BLOCK
- Ecosystem registry validation failure → BLOCK
- Review artifact validation failure (when review artifacts touched) → BLOCK
- Governance manifest missing required fields → BLOCK
- Authority vocabulary violations → BLOCK

### Mapped Workflows / Scripts
- `strategy-compliance.yml` → `scripts/check_strategy_compliance.py`
- `3ls-registry-gate.yml` → `spectrum_systems/governance/registry_drift_validator.py`
- `review-artifact-validation.yml` → `scripts/run_review_artifact_validation.py`
- `ecosystem-registry-validation.yml` → `scripts/validate_ecosystem_registry.py`
- `cross-repo-compliance.yml` (subset — manifest validation)
- Gate runner: `scripts/run_governance_gate.py` (new)

### Invariants Protected
- No governance surface change may be promoted without validation
- System registry schema gaps block promotion
- Review artifacts are always valid before merge
- Authority shape violations are caught before main

### Pass Example
```json
{
  "gate_name": "governance_gate",
  "status": "allow",
  "strategy_compliance": "pass",
  "registry_drift": "none",
  "ecosystem_validation": "pass"
}
```

### Fail Example
```json
{
  "gate_name": "governance_gate",
  "status": "block",
  "failure_summary": {
    "gate_name": "governance_gate",
    "failure_class": "registry_violation",
    "root_cause": "System FRE missing schema contract in contracts/schemas/",
    "blocking_reason": "registry-compliance: 1 system with missing schema",
    "next_action": "Add fre_result.schema.json to contracts/schemas/",
    "affected_files": ["docs/architecture/system_registry.md"],
    "failed_command": "spectrum_systems/governance/registry_drift_validator.py",
    "artifact_refs": ["outputs/gates/governance_gate_result.json"]
  }
}
```

---

## Gate 5 — Certification Gate (Nightly / Release)

### Purpose
Verify that the full system is certifiable: replay checks, lineage checks, promotion readiness, GOV-10 done certification, fail-closed behavior checks, and required artifact presence. This gate answers: "Is this ready for promotion to main / release?"

### Fast PR Mode
On PRs touching certification-relevant paths (SEL, CDE, eval, replay), a fast subset runs:
- SEL replay gate smoke check
- Eval CI gate with example fixtures
- Governed failure injection gate

### Deep Nightly Mode
Full certification suite:
- Complete SEL replay gate
- Complete eval CI gate with full dataset
- Done certification checks (GOV-10)
- Lineage validation
- Chaos/fail-closed tests
- Artifact boundary stress tests
- Full governance + promotion checks

### Inputs (fast mode)
- `contracts/examples/eval_run.json`, `contracts/examples/eval_case.json`
- `contracts/examples/continuation_decision_record.json`
- `contracts/examples/decision_bundle.json`

### Inputs (deep mode)
- Full eval case library
- Historical run artifacts
- Release policy: `data/policy/eval_release_policy.json`

### Outputs
- `outputs/gates/certification_gate_result.json`
- `outputs/sel_replay_gate/` artifacts
- `outputs/eval_ci_gate/` artifacts
- `outputs/governed_failure_injection/` artifacts

### Artifact Schema
`contracts/schemas/certification_gate_result.schema.json`

### Fail-Closed Conditions
- SEL replay gate BLOCK → BLOCK
- Eval CI gate failure → BLOCK
- `done_certification_record` missing when required → BLOCK
- Lineage chain broken → BLOCK
- Replay mismatch → BLOCK
- Promotion readiness == false → BLOCK (nightly/release mode)
- Any fail-closed test failure → BLOCK

### Mapped Workflows / Scripts
- `lifecycle-enforcement.yml` (`eval-ci-gate`, `sel-replay-gate`, `governed-failure-injection-gate`)
- `release-canary.yml` → `scripts/run_release_canary.py`
- `scripts/run_eval_ci_gate.py`
- `scripts/run_sel_orchestration.py`
- `scripts/run_sel_replay_gate.py`
- `scripts/run_governed_failure_injection.py`
- `scripts/run_lineage_validation.py`
- Gate runner: `scripts/run_certification_gate.py` (new)

### Invariants Protected
- No promotion without a passing certification
- Replay mismatch always blocks
- Eval coverage gaps are surfaced, not silently accepted
- Lineage chain must be unbroken

---

## PR Gate Orchestration

For every PR, the gates run in this order:

```
Contract Gate → Test Selection Gate → Runtime Test Gate → Governance Gate
                                              ↓
                                   (if cert paths touched)
                                   Certification Gate (fast mode)
```

Final result: `outputs/pr_gate/pr_gate_result.json`

The PR gate orchestrator (`scripts/run_pr_gate.py`) is a thin coordinator — it calls gates in order, collects results, and emits the final artifact. It contains no policy logic.

---

## Gate Runtime Budgets

| Gate | Fast PR Budget | Nightly Budget |
|---|---|---|
| Contract Gate | ≤ 60s | ≤ 90s |
| Test Selection Gate | ≤ 10s | ≤ 10s |
| Runtime Test Gate | ≤ 120s | ≤ 900s (full suite) |
| Governance Gate | ≤ 30s (path-filtered) | ≤ 120s |
| Certification Gate (fast) | ≤ 60s | N/A |
| Certification Gate (deep) | N/A | ≤ 600s |
| **Total Fast PR** | **≤ 4 min** | N/A |
| **Total Nightly** | N/A | **≤ 30 min** |
