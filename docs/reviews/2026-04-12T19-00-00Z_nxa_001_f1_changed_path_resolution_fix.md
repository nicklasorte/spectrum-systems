# NXA-001-F1 Changed-Path Resolution Fix Review — 2026-04-12T19:00:00Z

## 1. Exact blocker found
Preflight BLOCK was caused by `WRAPPER_CHANGED_PATHS_MISMATCH` during governed required-context enforcement, after invalid base/head refs forced fallback behavior and wrapper/preflight changed-path surfaces diverged.

## 2. Root cause
- Invalid CI ref ranges made exact diff resolution unreliable.
- Preflight and wrapper changed-path evidence could diverge (stale wrapper changed_paths vs resolved preflight paths), producing authoritative-wrapper mismatch blocks.
- Empty/insufficient changed-path evidence in degraded modes needed clearer canonical classification and reason coding.

## 3. Files changed
- `scripts/run_contract_preflight.py`
- `tests/test_contract_preflight.py`
- `docs/review-actions/PLAN-NXA-001-F1-2026-04-12.md`
- `docs/reviews/2026-04-12T19-00-00Z_nxa_001_f1_changed_path_resolution_fix.md`

## 4. Automated hardening added
- Added changed-path reason-code classification (`invalid_git_ref_range`, `degraded_changed_path_mode`, `insufficient_changed_path_evidence`, `empty_changed_path_surface`).
- Added wrapper-based degraded changed-path recovery when diff trust is insufficient and wrapper changed_paths are trustworthy/non-empty.
- Added wrapper/preflight changed-path synchronization to prevent stale wrapper mismatch blocks (`WRAPPER_CHANGED_PATHS_MISMATCH`) while preserving governed validation.
- Added explicit detection metadata fields for trust/bounded reasoning and mode outcomes.

## 5. Why the fix preserves contract discipline
- No schema weakening and no bypass paths.
- Empty or insufficient changed-path evidence still blocks quickly.
- Degraded mode is explicit, bounded, and traceable.
- Governance defects (policy/enforcement/authority mismatch) still block fail-closed.

## 6. Tests run and results
- `pytest tests/test_contract_preflight.py -q` → **64 passed**
- `pytest tests/test_contract_bootstrap.py -q` → **2 passed**
- `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q` → **117 passed**
- `python scripts/run_contract_enforcement.py` → **failures=0 warnings=0**
- `python scripts/run_contract_preflight.py --base-ref "793637096aa8620c7cadfacd091c75e52d2652bc" --head-ref "99f84d53b425901217eeb8ee6b1c01905a38b742" --output-dir outputs/contract_preflight --execution-context pqx_governed --pqx-wrapper-path outputs/contract_preflight/preflight_pqx_task_wrapper.json --authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json` → **passed** (`strategy_gate_decision=ALLOW`)

## 7. Remaining seams
If future governance requires report-level reason codes to also be serialized in the strict preflight contract artifact, promote through explicit schema versioning.
