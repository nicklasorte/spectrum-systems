# FPG-001 Preflight Diff-Resolution Hardening Review — 2026-04-12T18:00:00Z

## 1. Root cause
Invalid `git diff <base>..<head>` ranges triggered fallback paths that could degrade into noisy/slow detection and produce unstable operational behavior. The preflight path needed a bounded, canonical diff ladder with explicit trust signaling.

## 2. Runtime/performance cause
Fallback could continue into broader detection behavior after repeated invalid refs. Without strict bounded termination semantics, invalid-ref scenarios consumed unnecessary time and risked non-trustworthy changed-path surfaces.

## 3. Files changed
- `scripts/run_contract_preflight.py`
- `tests/test_contract_preflight.py`
- `docs/review-actions/PLAN-FPG-001-2026-04-12.md`
- `docs/reviews/2026-04-12T18-00-00Z_fpg_001_preflight_diff_resolution_hardening.md`

## 4. New bounded fallback behavior
- Added timeout-aware command execution for diff/status paths.
- Implemented deterministic, centralized ref tracking with status outcomes.
- Implemented bounded ladder termination: if bounded tiers fail to produce trustworthy governed paths, detection returns `insufficient_diff_evidence` quickly (no broad full-governed scan).
- Added trust/bounded metadata (`trust_level`, `bounded_runtime`, successful/failed mode summaries) in report detection metadata.
- Preflight now blocks on insufficient diff trust evidence explicitly.

## 5. Why the fix preserves contract discipline
- No schema weakening and no bypass.
- `trace.refs_attempted` remains explicit and unique.
- Fail-closed behavior remains for real governance issues and now also for insufficient changed-path trust evidence.

## 6. Tests run and results
- `pytest tests/test_contract_preflight.py -q` → **61 passed**
- `pytest tests/test_contract_bootstrap.py -q` → **2 passed**
- `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q` → **117 passed**
- `python scripts/run_contract_enforcement.py` → **failures=0 warnings=0**
- `python scripts/run_contract_preflight.py --base-ref "793637096aa8620c7cadfacd091c75e52d2652bc" --head-ref "99f84d53b425901217eeb8ee6b1c01905a38b742" --output-dir outputs/contract_preflight --execution-context pqx_governed --pqx-wrapper-path outputs/contract_preflight/preflight_pqx_task_wrapper.json --authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json` → **passed** (`strategy_gate_decision=ALLOW`)

## 7. Remaining seams
- If future governance requires persistence of ref-resolution detail in contract artifacts (not only report metadata), promote via explicit schema versioning.
