# FPR-001 Preflight Ref-Resolution Fix Review — 2026-04-12T17:00:00Z

## 1. Root cause
`run_contract_preflight.py` could accumulate duplicate revision attempt strings during fallback/ref-resolution paths, which propagated into `trace.refs_attempted`. Since contract schema enforces `uniqueItems: true`, artifact validation could fail for malformed trace metadata rather than true governance failures.

## 2. Files changed
- `scripts/run_contract_preflight.py`
- `tests/test_contract_preflight.py`
- `docs/review-actions/PLAN-FPR-001-2026-04-12.md`
- `docs/reviews/2026-04-12T17-00-00Z_fpr_001_preflight_ref_resolution_fix.md`

## 3. Automated hardening added
- Added canonical `_RefAttemptTracker` with stable dedupe and status transitions (`attempted`, `failed_invalid_revision`, `succeeded`, `fallback_used`).
- Added `_stable_unique_strings` normalization before report/artifact emission so `refs_attempted` is always schema-safe and deterministic.
- Extended detection metadata with `ref_resolution_records` for debugging while preserving contract artifact shape.
- Added regression tests for:
  - uniqueness + stable ordering of `refs_attempted`,
  - complete git diff failure fallback behavior,
  - artifact emission normalization when duplicate refs are injected from detection output.

## 4. Why the fix preserves contract discipline
- No schema weakening or uniqueness relaxation.
- Trace recording remains explicit and richer (not skipped).
- Fail-closed behavior for real governance defects is unchanged; only malformed trace duplication is eliminated.

## 5. Tests run and results
- `pytest tests/test_contract_preflight.py -q` → **60 passed**
- `pytest tests/test_contract_bootstrap.py -q` → **2 passed**
- `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q` → **117 passed**
- `python scripts/run_contract_enforcement.py` → **failures=0 warnings=0**
- `python scripts/run_contract_preflight.py --base-ref "793637096aa8620c7cadfacd091c75e52d2652bc" --head-ref "99f84d53b425901217eeb8ee6b1c01905a38b742" --output-dir outputs/contract_preflight --execution-context pqx_governed --pqx-wrapper-path outputs/contract_preflight/preflight_pqx_task_wrapper.json --authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json` → **passed** (`strategy_gate_decision=ALLOW`)

## 6. Remaining seams
- `ref_resolution_records` currently lives in report metadata only; if long-term replay contracts require it, promote via governed schema versioning in a dedicated contract revision.
