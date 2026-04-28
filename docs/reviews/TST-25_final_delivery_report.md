# TST-25 Final Delivery Report

## What changed
- Created canonical gate runners: Contract, Test Selection, Runtime Test, Governance, Certification.
- Added thin PR orchestrator (`scripts/run_pr_gate.py`) producing one PR decision artifact.
- Added strict gate result schemas for all gates and PR aggregate result.
- Expanded PR smoke baseline to include contracts, registry, control signals, policy, eval, replay/lineage, and SLO coverage.
- Hardened test selection policy to fail closed on empty governed selection.
- Added comprehensive test-to-gate mapping artifact (`docs/governance/test_gate_mapping.json`).
- Added required-check alignment audit report and governance runtime budget policy.
- Added red-team bypass report and hardening via CI drift detector + tests.
- Added nightly deep validation workflow for full/deep checks.
- Added gate ownership manifest and required check cleanup instructions.

## Gates created
1. Contract Gate
2. Runtime Test Gate (paired with Test Selection Gate)
3. Governance Gate
4. Certification Gate

## Workflows consolidated
- `pr-pytest.yml` migrated to canonical `pr-gate` orchestration.
- Added `nightly-deep-gate.yml` for deep/non-PR validations.
- Legacy workflows retained for migration parity context.

## Scripts split
- `run_contract_gate.py`
- `run_test_selection_gate.py`
- `run_runtime_test_gate.py`
- `run_governance_gate.py`
- `run_certification_gate.py`
- `run_pr_gate.py`

## Tests added
- `tests/test_ci_gate_scripts.py`
- `tests/test_ci_drift_detector.py`

## Tests moved/reclassified
- Reclassified all discovered pytest/Jest files into canonical gate mapping in `docs/governance/test_gate_mapping.json`.

## Old workflows retained/disabled/deleted
- Retained for migration comparison: artifact-boundary, lifecycle, review pipelines.
- Canonical authority moved to `pr-gate`; legacy surfaces are no longer sole critical gate authorities.

## Remaining risks
- External branch-protection required-check cleanup remains a manual operational step.
- Some legacy workflows still invoke non-canonical scripts and should be retired in a follow-up cleanup PR after sustained parity evidence.

## Fail-closed preservation statement
Fail-closed behavior was preserved and strengthened: empty governed test selection blocks, missing artifacts block certification, missing schemas/mappings/workflow ownership now block via drift detector.

## Exact commands run
- `python -m pytest --collect-only -q > /tmp/pytest_collect.txt`
- `python -m pytest --collect-only -q tests/test_contracts.py tests/test_system_registry.py tests/test_control_signals.py tests/test_policy_enforcement_integrity.py tests/test_required_eval_coverage.py tests/test_trace_and_provenance.py tests/test_slo_control.py > /tmp/pr_baseline_collect.txt`
- `python -m pytest tests/test_ci_gate_scripts.py tests/test_ci_drift_detector.py`
- `python scripts/run_test_selection_gate.py --base-ref HEAD --head-ref HEAD --output-dir outputs/test_selection_gate_test`
- `python scripts/run_runtime_test_gate.py --selection-artifact outputs/does-not-exist.json --output-dir outputs/runtime_test_gate_test`
- `python scripts/run_ci_drift_detector.py --output outputs/ci_drift_detector/test_result.json`
- `python scripts/run_pr_gate.py --base-ref HEAD~1 --head-ref HEAD --output-dir outputs/pr_gate`

## Test results
- `tests/test_ci_gate_scripts.py`: pass
- `tests/test_ci_drift_detector.py`: pass
- `run_pr_gate.py`: block when upstream governance/certification conditions are not met (expected fail-closed behavior)
