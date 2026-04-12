# FAP-001 Preflight Fix Review — 2026-04-12T16:00:00Z

## 1. Exact blocker found in preflight
- `MALFORMED_PQX_TASK_WRAPPER` in `pqx_required_context_enforcement` with error: missing file at `outputs/contract_preflight/preflight_pqx_task_wrapper.json`.
- Additional producer regression surfaced in preflight test execution: `tests/test_next_governed_cycle_runner.py` failed because NX integration required missing signal groups.

## 2. Root cause
- Preflight treated missing `--pqx-wrapper-path` input file as malformed without canonical bootstrap, causing governed-context block.
- NXA-001 NX integration assumed fully populated `nx_signals`, but canonical cycle tests execute without explicit NX signal payloads.

## 3. Files changed
- `scripts/run_contract_preflight.py`
- `spectrum_systems/modules/runtime/nx_governed_system.py`
- `tests/test_contract_preflight.py`
- `tests/test_next_governed_cycle_runner.py`
- `docs/review-actions/PLAN-FAP-001-2026-04-12.md`
- `docs/reviews/2026-04-12T16-00-00Z_fap_001_preflight_fix_review.md`

## 4. Why the fix is canonical and non-bypass
- Preflight now bootstraps a canonical `codex_pqx_task_wrapper` from the repository’s governed example only when wrapper file input is missing and execution context is `pqx_governed`; it still runs full required-context enforcement and remains fail-closed.
- Wrapper bootstrap injects actual changed paths and supplied authority evidence ref, preserving governed context semantics rather than bypassing checks.
- NX runtime now deterministically fills required NX signal/trust fields from safe defaults when omitted, preserving in-cycle execution and existing producer compatibility without relaxing authority boundaries.

## 5. Tests/preflight commands run and results
- `python scripts/run_contract_preflight.py --base-ref "793637096aa8620c7cadfacd091c75e52d2652bc" --head-ref "99f84d53b425901217eeb8ee6b1c01905a38b742" --output-dir outputs/contract_preflight --execution-context pqx_governed --pqx-wrapper-path outputs/contract_preflight/preflight_pqx_task_wrapper.json --authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json` → **passed** (`strategy_gate_decision=ALLOW`).
- `pytest tests/test_next_governed_cycle_runner.py tests/test_contract_preflight.py tests/test_nx_governed_system.py tests/test_apx_module_system.py -q` → **81 passed**.
- `pytest tests/test_contract_bootstrap.py -q` → **2 passed**.
- `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q` → **117 passed**.
- `python scripts/run_contract_enforcement.py` → **failures=0 warnings=0**.

## 6. Remaining follow-up seams
- If CI requires wrapper generation from task metadata (not example bootstrap), add an upstream wrapper-producer step before preflight and keep this bootstrap as deterministic fallback.
- Expand APX artifact contracts if/when APX module runtime artifacts move into governed contract surfaces.

## Terminal summary
- blocker category fixed: `MALFORMED_PQX_TASK_WRAPPER` (+ NX producer regression)
- files changed: 6
- tests run: preflight + 4 pytest commands + contract enforcement script
- preflight pass/fail: **PASS**
- remaining seams: upstream wrapper-producer stage hardening; future APX contract surface expansion
