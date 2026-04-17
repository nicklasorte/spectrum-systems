# PRA-NSX-PRG-001-HARDENING-001 Delivery Report

## 1. Intent
Apply a surgical registry-alignment fix by removing the new PRA failure artifact family and restoring a schema-valid fail-closed path within the existing `pra_pull_request_resolution_record` contract.

## 2. Root cause of registry failure
The prior hardening introduced `pra_pull_request_resolution_failure_record` (schema/example/manifest), which created a new PRA-owned artifact family and triggered `PROTECTED_AUTHORITY_VIOLATION` and `SHADOW_OWNERSHIP_OVERLAP` in system registry guard.

## 3. Why the new PRA failure artifact was removed
To preserve canonical PRA ownership boundaries and avoid expanding PRA into a new failure-artifact subsystem, the companion failure artifact family was removed and its manifest registration was deleted.

## 4. How fail-closed behavior was preserved within the existing PRA resolution artifact
The PR-resolution exception path now emits a schema-valid `pra_pull_request_resolution_record` with explicit unresolved semantics:
- `state = "unresolved"`
- `selected_pr_reason = "resolution_failed:<reason>"`
- `pr_number = 0` when no PR is resolvable
The runner still exits non-zero (`return 1`) to halt downstream execution.

## 5. Files modified
- `contracts/schemas/pra_pull_request_resolution_record.schema.json`
- `contracts/examples/pra_pull_request_resolution_record.json` (no shape change required; remains valid)
- `contracts/standards-manifest.json`
- `scripts/run_pra_nsx_prg_automation.py`
- `spectrum_systems/modules/runtime/pra_nsx_prg_loop.py`
- `tests/test_pra_nsx_prg_loop.py`
- `docs/reviews/PRA-NSX-PRG-001-HARDENING-001_delivery_report.md`

## 6. Tests updated
Updated `tests/test_pra_nsx_prg_loop.py` to assert that fail-closed resolution paths (empty PR list and unmatched override) emit schema-valid **existing** resolution artifacts and preserve non-zero exit behavior.

## 7. Validation commands run
1. `python scripts/run_system_registry_guard.py --base-ref "95add616554b44c484916dd0cdeb3275d1f21ac6" --head-ref "4f1fb79b84db3d75da5edfeaa2f251832ff920ee" --output outputs/system_registry_guard/system_registry_guard_result.json`
2. `pytest -q tests/test_pra_nsx_prg_loop.py`
3. `pytest -q tests/test_contracts.py`
4. `pytest -q tests/test_contract_enforcement.py`
5. `python scripts/run_contract_enforcement.py`
6. `pytest -q`

## 8. Results
All required commands passed. Registry guard no longer fails on PRA overlap/protected authority for this fix scope.

### Concise terminal summary
- Removed overlapping artifact family: `pra_pull_request_resolution_failure_record` (schema/example/manifest entry removed).
- Repaired existing failure-path artifact: fail path now emits valid `pra_pull_request_resolution_record` with unresolved/failure reason semantics.
- Registry guard result: pass.
- Targeted tests result: pass.
- Full pytest result: pass.

## 9. Remaining gaps
This fix intentionally does not broaden PRA behavior beyond resolution artifacts; live PR-source transport hardening remains a separate slice.

## 10. Recommended next slice
Close remaining workflow-front-door routing gaps in repository workflows so CDE posture can move from halt conditions to bounded continuation when appropriate.
