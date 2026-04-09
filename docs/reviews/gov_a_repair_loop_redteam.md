# GOV-A Repair Loop Red-Team — 2026-04-09

## 1. Executive Verdict
- Is the loop enforceable? **NO**
- **Reason:** The TPA gate “authority” can be forged locally and accepted as valid, which allows policy-unauthenticated fix execution to reach PQX inside the governed loop.

## 2. Attack Results

### Attack 1 — Review bypass
- **result:** **FAILED** (no bypass found in the governed repair-loop path)
- **explanation:** In the one-cycle repair loop, PQX execution is followed by an unconditional call to `run_review_queue_executor(...)`; there is no success path that returns without running RQX post-fix review. The loop status is then derived from that review verdict. In the bundle path, bundle execution also emits a bounded post-execution RQX review artifact via `_emit_bundle_post_execution_review(...)` after record emission. Exploit attempt did not produce a completion path that avoids RQX in-scope.

### Attack 2 — Fix bypass
- **result:** **FAILED** (no direct RQX→PQX fix execution path without TPA in-loop)
- **explanation:** `run_review_fix_execution_cycle(...)` hard-checks TPA before executor invocation and blocks PQX execution when TPA is not allow. Bundle fix execution also requires a TPA gate bundle per pending fix and validates authoritative provenance before fix execution. Direct RQX→PQX fix routing inside this seam is blocked.

### Attack 3 — Fake TPA linkage
- **result:** **SUCCEEDED — BLOCKER**
- **explanation:** The authoritative TPA check is integrity-only, not authenticity-bound. `validate_tpa_gate_authoritative_provenance(...)` accepts any artifact under `artifacts/tpa_authority/<artifact_id>.json` if payload equality and SHA-256 token match. The token is computed by public deterministic function `compute_tpa_gate_provenance_token(...)` over non-secret fields. An attacker/caller can forge both the in-request `tpa_slice_artifact` and the authority file+token, then pass validation with zero proof of real TPA policy evaluation. Exact exploit path:
  1. Craft `review_fix_execution_request_artifact.tpa_slice_artifact` with `phase=gate` and allow-like fields.
  2. Compute token using `compute_tpa_gate_provenance_token(...)`.
  3. Write forged authority artifact to `artifacts/tpa_authority/<artifact_id>.json` including that token.
  4. Call `run_review_fix_execution_cycle(...)` (or bundle fix path); provenance validation passes and PQX execution proceeds.

### Attack 4 — RQX role drift
- **result:** **FAILED** (RQX remained bounded in reviewed seam)
- **explanation:** `review_queue_executor` emits review artifacts, optional fix-slice artifact, and operator handoff artifact; it does not execute fixes or grant closure authority. `review_handoff_disposition` classifies handoffs and explicitly marks `execution_triggered=False` and `rqx_cycle_reentry_triggered=False`. RQX behavior is bounded in the examined seam.

### Attack 5 — Unresolved recursion
- **result:** **FAILED** (no hidden recursion path found)
- **explanation:** Unresolved outcomes (`completed_fix_still_required`, `completed_not_safe_to_merge`, `blocked_by_tpa`, `blocked_checkpoint_missing`, `execution_failed`) emit terminal result + operator handoff and stop. The disposition classifier emits scheduling/ownership signals only; it does not re-enter PQX/RQX automatically. No hidden auto-recursive reentry was found.

### Attack 6 — Bundle inconsistency
- **result:** **PARTIAL SUCCESS — BLOCKER via shared TPA-forgery weakness**
- **explanation:** Bundle fix execution itself enforces a TPA gate artifact per fix and validates provenance before running fixes. However, it reuses the same forgeable provenance mechanism as Attack 3 (`validate_tpa_gate_authoritative_provenance(...)`). Therefore, a bundle-level fix path can be policy-bypassed by forged TPA authority artifacts even though structural gating exists.

### Attack 7 — Drift scenario
- **result:** **SUCCEEDED — HIGH**
- **explanation:** Realistic drift risk is high because low-level execution entrypoints remain callable without embedded RQX/TPA enforcement (`run_pqx_slice(...)`, `execute_fix_step(...)`). Current safety depends on callers using the correct orchestrator seam. A new wrapper/caller can reintroduce direct execution or ungated fix behavior by bypassing `run_review_fix_execution_cycle(...)` / bundle orchestration contracts.

## 3. Weakest Point
- **Single most fragile component:** `validate_tpa_gate_authoritative_provenance(...)` trust model (file-presence + deterministic hash) is not cryptographic proof of TPA authority and is trivially forgeable by any caller with write access to repo artifacts.

## 4. Final Recommendation
- **DO NOT MOVE ON**
