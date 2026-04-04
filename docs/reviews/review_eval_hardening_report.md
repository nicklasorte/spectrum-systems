# REPORT-003 — Review → Eval → Control Hardening Audit

Date: 2026-04-04
Scope: `review_signal_extractor.py`, `review_eval_bridge.py`, `evaluation_control.py`, `evaluation_auto_generation.py`

## Executive Summary
This audit hardened the highest-risk trust boundary in the runtime spine without changing control-loop ownership or adding capability. The hardening focused on precedence integrity, deterministic canonicalization, and fail-closed behavior for review-derived eval influence.

## Findings and Minimal Fixes

| ID | Severity | Failure mode | Evidence | Minimal fix applied |
| --- | --- | --- | --- | --- |
| REPORT-003-F01 | S1 | Replay mismatch could resolve to `block` instead of required `freeze`, weakening replay-boundary semantics. | `spectrum_systems/modules/runtime/evaluation_control.py` replay control path (`consistency_status`, final decision override). | Added explicit precedence override: replay mismatch now resolves to `system_response=freeze` with deny semantics unless a stronger required-signal block already applies. |
| REPORT-003-F02 | S1 | Indeterminate replay signals could resolve as non-freeze depending on budget/rationale merge. | `spectrum_systems/modules/runtime/evaluation_control.py` (`indeterminate_failure` handling). | Added explicit indeterminate precedence override to force deny+freeze unless required-signal/review-fail block is already active. |
| REPORT-003-F03 | S2 | Canonical dedupe in review/eval seams used sorted set behavior that could reorder source findings. | `review_signal_extractor.py`, `review_eval_bridge.py`, `evaluation_auto_generation.py`. | Replaced sort-based dedupe with `dedupe_preserve_order` in trust-boundary lists. |
| REPORT-003-F04 | S2 | Hash canonicalization was reimplemented ad hoc in several paths. | Same module set above. | Introduced explicit `canonical_json` helper in scoped modules and used sha256 over canonical bytes. |
| REPORT-003-F05 | S1 | Missing required review signal/type must hard-block regardless of baseline replay posture. | `evaluation_control.py` review required checks. | Preserved and tightened precedence ordering so missing-required checks remain terminal block decisions. |
| REPORT-003-F06 | S1 | Review-derived eval generation must fail closed when mapping token absent (`eval_family`). | `evaluation_auto_generation.py` `_extract_review_eval_family`. | Verified fail-closed exception path and added/retained tests to assert no token guessing. |

## Bypass Detection Results

### Control entry points
- `build_evaluation_control_decision(...)` is the canonical mapper in `evaluation_control.py`.
- `run_control_loop(...)` in `control_loop.py` consumes replay/failure signals and routes through `build_evaluation_control_decision(...)`.
- Runtime control integration (`control_integration.py`) consumes the emitted `evaluation_control_decision` output rather than bypassing control.

### Audit conclusions
- PQX/runtime control flow calls eval/replay artifacts before control decision emission.
- No direct promotion path was introduced in the scoped hardening changes.
- Required review-eval presence gating remains fail-closed (`missing_required_signal` → deny/block).

## Precedence Integrity (post-hardening)
Enforced order in effective decision outcomes:
1. Missing required signal/type → `block`
2. Trace/schema invalidity → fail closed (error raised; no allow)
3. Replay mismatch → `freeze`
4. Required review eval fail → `block`
5. Indeterminate (when not already blocked by required-signal/review-fail) → `freeze`

## Determinism and Fail-Closed Guarantees
- Canonical hashing uses `sha256(canonical_json(...))` in scoped modules.
- Dedupe order uses `dedupe_preserve_order(...)`.
- Malformed review signal and malformed replay/control inputs fail closed with explicit exceptions.
- Missing eval-family token in review critical findings fails closed (no heuristic mapping).

## Contract Discipline Verification
Validated through contract test/enforcement suite:
- Draft 2020-12 schema loading/validation intact.
- Required fields and additional-properties constraints remain enforced by contract tests.

## Residual Risk
- Existing downstream tests outside the immediate trust-boundary suite required expectation updates where replay mismatch/indeterminate outcomes are now freeze-class by design.
- Risk level after patch: **S2 (managed)**; no bypass path introduced and no parallel authority added.
