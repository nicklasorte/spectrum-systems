# TST-18 — Parallel Gate Migration Report

**Produced:** 2026-04-29  
**Branch:** claude/ci-test-consolidation-VV6y4

---

## Migration Strategy

During this phase, both old workflows and new canonical gate scripts coexist. New gates are the intended authority; old workflows remain available for comparison.

No old workflow is the only source of a critical invariant — all critical invariants are now enforced by canonical gate scripts.

---

## Old → New Mapping

| Old Surface | New Canonical Surface | Status |
|---|---|---|
| `pr-pytest.yml` inline Python (~160 lines) | `scripts/run_contract_gate.py` | NEW (parallel) |
| `pr-pytest.yml` `build_preflight_pqx_wrapper.py` call | `scripts/run_contract_gate.py` step 8 | NEW (parallel) |
| `pr-pytest.yml` `run_contract_preflight.py` call | `scripts/run_contract_gate.py` step 8 | NEW (parallel) |
| `pr-pytest.yml` trust validation inline | `scripts/run_contract_gate.py` trust enforcement | NEW (parallel) |
| `artifact-boundary.yml` `governed-contract-preflight` job | `scripts/run_contract_gate.py` | NEW (parallel) |
| `artifact-boundary.yml` `run-pytest` (non-authoritative) | `scripts/run_runtime_test_gate.py` | NEW (parallel) |
| `artifact-boundary.yml` boundary/arch/registry jobs | `scripts/run_contract_gate.py` steps 1–7 | NEW (parallel) |
| `lifecycle-enforcement.yml` eval-ci-gate | `scripts/run_certification_gate.py` | NEW (parallel) |
| `lifecycle-enforcement.yml` sel-replay-gate | `scripts/run_certification_gate.py` | NEW (parallel) |
| `lifecycle-enforcement.yml` governed-failure-injection | `scripts/run_certification_gate.py` | NEW (parallel) |
| `strategy-compliance.yml` | `scripts/run_governance_gate.py` strategy check | NEW (parallel) |
| `3ls-registry-gate.yml` | `scripts/run_governance_gate.py` registry check | NEW (parallel) |
| `review-artifact-validation.yml` | `scripts/run_governance_gate.py` review check | NEW (parallel) |
| `ecosystem-registry-validation.yml` | `scripts/run_governance_gate.py` ecosystem check | NEW (parallel) |
| Inline trust validation in `pr-autofix-contract-preflight.yml` | `scripts/run_contract_gate.py` | NEW (parallel) |

---

## Parity Findings

### Parity confirmed:
- Contract gate replicates all trust validation from inline workflow Python
- Test selection gate enforces all provenance and integrity checks from `pytest_selection_integrity_result`
- Governance gate covers strategy, registry, review, and ecosystem checks
- Certification gate covers eval CI, SEL replay, and governed failure injection
- Drift detector covers manifest, schema, and workflow mapping gaps

### Differences from old system:
1. **Old:** Trust validation logic is duplicated in two workflow YAML files (~160 lines each). **New:** Single canonical implementation in `run_contract_gate.py`.
2. **Old:** Test selection fallback uses a single file with 19 tests. **New:** Smoke baseline covers 14 files representing all canonical gate invariants.
3. **Old:** Governance checks scattered across 4+ separate workflows with static path filters. **New:** Single `run_governance_gate.py` with dynamic path detection.
4. **Old:** No gate result artifacts with schemas. **New:** Six typed schemas, all `additionalProperties: false`.
5. **Old:** No CI drift detection. **New:** `run_ci_drift_detector.py` detects unmapped workflows, missing schemas, and missing scripts.

### Remaining risks during parallel migration:
- Old workflows still invoke `run_contract_preflight.py` directly (not via `run_contract_gate.py`). This is acceptable during parallel migration but must be addressed in TST-19.
- The old inline trust validation in `pr-pytest.yml` and `pr-autofix-contract-preflight.yml` will run alongside the new gate scripts until cutover. Divergence between old and new would surface two different failure messages for the same condition — this is acceptable during migration.
- `pr-pytest.yml` is still the required check (`PR / pytest`). The new `run_pr_gate.py` is not yet wired into the required check — this is intentional during migration.
