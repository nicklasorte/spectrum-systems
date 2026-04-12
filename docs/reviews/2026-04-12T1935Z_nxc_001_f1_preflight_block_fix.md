# NXC-001-F1 Preflight Block Fix — 2026-04-12T19:35Z

## 1) Exact blocker found
- Blocker category: **invalid contract/reference/path** + **module admission gate failure**.
- Exact blocker from generated preflight report:
  - `MALFORMED_PQX_TASK_WRAPPER`
  - required-surface gap for `scripts/run_enforced_execution.py` (no deterministic evaluation target mapping).

## 2) Root cause
1. `scripts/build_preflight_pqx_wrapper.py` wrote `changed_path_resolution` into the wrapper root object.
   The `codex_pqx_task_wrapper` contract disallows extra root properties (`additionalProperties: false`), so wrapper validation failed in PQX required-context enforcement.
2. `scripts/run_enforced_execution.py` changed but `run_contract_preflight` had no required-surface test override mapping for it, causing a required evaluation mapping gap.

## 3) Files changed
- `docs/review-actions/PLAN-NXC-001-F1-2026-04-12.md`
- `scripts/build_preflight_pqx_wrapper.py`
- `scripts/run_contract_preflight.py`
- `tests/test_build_preflight_pqx_wrapper.py`
- `docs/reviews/2026-04-12T1935Z_nxc_001_f1_preflight_block_fix.md`

## 4) Why the fix is canonical
- Governance checks were not weakened; fail-closed behavior was preserved.
- Wrapper now remains schema-valid while changed-path resolution metadata is emitted in a dedicated sidecar artifact (`preflight_changed_path_resolution.json`) instead of violating contract shape.
- Required-surface mapping was tightened for changed governed script paths to satisfy deterministic evaluation expectations.

## 5) Tests and preflight commands run
1. `pytest tests/test_build_preflight_pqx_wrapper.py tests/test_contract_preflight.py tests/test_execution_contracts.py -q`
2. `python scripts/build_preflight_pqx_wrapper.py --base-ref "aaa21d8d8ba8efa12cbae83364d3b98a3cd3be97" --head-ref "4420f77af6b1144bafe8261bc1b12a183d8c9bc5" --output outputs/contract_preflight/preflight_pqx_task_wrapper.json`
3. `python scripts/run_contract_preflight.py --base-ref "aaa21d8d8ba8efa12cbae83364d3b98a3cd3be97" --head-ref "4420f77af6b1144bafe8261bc1b12a183d8c9bc5" --output-dir outputs/contract_preflight --execution-context pqx_governed --pqx-wrapper-path outputs/contract_preflight/preflight_pqx_task_wrapper.json --authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json`
4. `pytest tests/test_contract_bootstrap.py -q`
5. `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q`
6. `python scripts/run_contract_enforcement.py`

## 6) Remaining seams
- The wrapper sidecar (`preflight_changed_path_resolution.json`) is currently emitted but not uploaded by workflow artifact collection.
- Broader roadmap slices (NXA groups outside NXC-001/F1) remain for follow-up PRs.
