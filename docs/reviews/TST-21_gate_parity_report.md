# TST-21 — Gate Parity Report

**Produced:** 2026-04-29  
**Branch:** claude/ci-test-consolidation-VV6y4

---

## Methodology

Parity was assessed by comparing the logic of old workflow steps against the equivalent logic in the new canonical gate scripts.

Full runtime-based parity testing (running both old and new against historical PRs) is not feasible in this environment — no CI runs are available. Structural parity is assessed by code review.

---

## Contract Gate Parity

| Old Check | New Equivalent | Parity? |
|---|---|---|
| `check_artifact_boundary.py` call | `run_contract_gate.py` step 1 | ✓ PARITY |
| `validate_module_architecture.py` call | `run_contract_gate.py` step 2 | ✓ PARITY |
| `validate_orchestration_boundaries.py` call | `run_contract_gate.py` step 3 | ✓ PARITY |
| `run_authority_shape_preflight.py` call | `run_contract_gate.py` step 4 | ✓ PARITY |
| `run_authority_drift_guard.py` call | `run_contract_gate.py` step 5 | ✓ PARITY |
| `run_system_registry_guard.py` call | `run_contract_gate.py` step 6 | ✓ PARITY |
| `run_authority_leak_guard.py` call | `run_contract_gate.py` step 7 | ✓ PARITY |
| `build_preflight_pqx_wrapper.py` call | `run_contract_gate.py` step 8a | ✓ PARITY |
| `run_contract_preflight.py` call | `run_contract_gate.py` step 8b | ✓ PARITY |
| Inline trust validation (~160 lines) | `run_contract_gate.py` trust section | ✓ PARITY (identical logic, refactored) |
| `WARN` is non-pass-equivalent | `run_contract_gate.py` WARN check | ✓ PARITY |
| Empty `selected_targets` blocks | `run_test_selection_gate.py` | ✓ PARITY |
| Provenance fields required | `run_test_selection_gate.py` | ✓ PARITY |
| Selection integrity required | `run_test_selection_gate.py` | ✓ PARITY |

---

## Test Selection Gate Parity

| Old Check | New Equivalent | Parity? |
|---|---|---|
| `pytest_execution_record_ref` present | `run_test_selection_gate.py` line | ✓ PARITY |
| `pytest_execution_record` file exists | `run_test_selection_gate.py` | ✓ PARITY |
| `executed == true` | `run_test_selection_gate.py` | ✓ PARITY |
| `selected_targets` non-empty | `run_test_selection_gate.py` | ✓ PARITY + IMPROVED (fallback) |
| All provenance fields present | `run_test_selection_gate.py` | ✓ PARITY |
| Commit SHA cross-record match | `run_test_selection_gate.py` | ✓ PARITY |
| Hash cross-record match | `run_test_selection_gate.py` | ✓ PARITY |
| Selection ref canonical path | `run_test_selection_gate.py` | ✓ PARITY |

---

## Governance Gate Parity

| Old Workflow | New Equivalent | Parity? |
|---|---|---|
| `strategy-compliance.yml` | `run_governance_gate.py` strategy check | ✓ PARITY |
| `3ls-registry-gate.yml` registry drift | `run_governance_gate.py` registry check | ✓ PARITY |
| `review-artifact-validation.yml` | `run_governance_gate.py` review check | ✓ PARITY |
| `ecosystem-registry-validation.yml` | `run_governance_gate.py` ecosystem check | ✓ PARITY |

**Note:** Old governance workflows use static YAML path filters; new governance gate uses dynamic Python path detection. The new approach is **stronger** — it catches files that fall through static path filter gaps (see B-12 in TST-16).

---

## Certification Gate Parity

| Old Workflow Job | New Equivalent | Parity? |
|---|---|---|
| `lifecycle-enforcement.yml` eval-ci-gate | `run_certification_gate.py` eval_ci_gate | ✓ PARITY |
| `lifecycle-enforcement.yml` sel-replay-gate | `run_certification_gate.py` sel_replay | ✓ PARITY |
| `lifecycle-enforcement.yml` governed-failure-injection | `run_certification_gate.py` failure_injection | ✓ PARITY |
| `release-canary.yml` smoke | Not in fast PR mode (release only) | ✓ PARITY (mode-separated) |

---

## Differences (New is Stronger)

1. **Smoke baseline expanded** — old: 1 file, 19 tests. New: 14 files covering all gate invariants.
2. **Gate result artifacts** — old: none structured. New: 6 typed schemas with `additionalProperties: false`.
3. **Drift detection** — old: none. New: `run_ci_drift_detector.py`.
4. **Governance gate path detection** — old: static YAML paths. New: dynamic Python detection.
5. **Failure messages** — old: scattered across output files. New: structured `failure_summary` in each gate result.

---

## Conclusion

Structural parity between old and new gate implementations is confirmed. The new canonical gate system is a strict improvement: same protection with better observability, less duplication, and explicit drift prevention.
