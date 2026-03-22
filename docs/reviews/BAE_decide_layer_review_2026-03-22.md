# BAE Decide Layer Review — 2026-03-22

## Scope
This review is strictly limited to the DECIDE layer behavior in the runtime control loop and its immediate decision-boundary contracts/tests.

Primary focus:
- `spectrum_systems/modules/runtime/evaluation_budget_governor.py` (legacy and control-loop budget decision logic)
- `spectrum_systems/modules/runtime/evaluation_control.py` (related deterministic/fail-closed decision mapper)
- `contracts/schemas/evaluation_budget_decision.schema.json`
- `contracts/schemas/evaluation_monitor_summary.schema.json`
- `tests/test_evaluation_budget_governor.py`
- `tests/test_evaluation_control_loop.py`

Minimal boundary inspection performed only to confirm call-path behavior:
- `scripts/run_evaluation_control_loop.py`

Out of scope:
- Any implementation fixes
- Schema redesign
- Upstream monitor aggregation redesign
- Non-DECIDE runtime modules except where needed to confirm decision boundaries

## Summary
- Overall status: **FAIL**

The DECIDE layer cannot currently be trusted as semantically correct, deterministic, and fail-closed for governance decisions. While schema validation and some explicit fail-closed branches exist, there are critical semantic-integrity gaps where contradictory summaries can produce internally inconsistent decisions (including `healthy`/`allow` paired with triggered adverse thresholds), and reproducibility is weakened by non-deterministic decision IDs/timestamps. The decision logic also relies on upstream `overall_status` without enforcing consistency against underlying SLI evidence, creating governance-risking false confidence when summaries are sparse, contradictory, or malformed-in-practice but schema-valid.

## Findings

### P1 (Critical — fail-open, semantically misleading, or governance-breaking)

- Finding
  - **Semantic contradiction accepted: `healthy`/`allow` decisions can still carry adverse triggered thresholds.**
  - In `build_validation_budget_decision`, status/response are set directly from `overall_status`, but a separate unconditional rule appends `output_paths_valid_rate_below_threshold` when `output_paths_valid_rate < 1.0`. This allows a decision artifact that is formally valid yet governance-semantically contradictory.
- Why it matters
  - Produces a misleading “safe” action with embedded adverse evidence, which can bypass governance intent and confuse downstream automation/human reviewers.
- Minimal fix
  - Enforce cross-field invariants at decision construction: if any hard adverse trigger is present, disallow `healthy`/`allow`; either escalate or fail closed.
- Affected files
  - `spectrum_systems/modules/runtime/evaluation_budget_governor.py`
  - `contracts/schemas/evaluation_budget_decision.schema.json`
  - `tests/test_evaluation_control_loop.py`

- Finding
  - **Control-loop mapping trusts `overall_status` without validating consistency to `aggregated_slis`, enabling false confidence from contradictory summaries.**
  - Example: `overall_status="warning"` with `bundle_validation_success_rate=1.0` still emits warning and a trigger named `bundle_validation_success_rate_below_1_0`.
- Why it matters
  - Decision layer can assert threshold breaches that are not present (or miss ones that are), breaking semantic trustworthiness and auditability.
- Minimal fix
  - Add explicit consistency checks between status and key SLI rates; contradictory combinations should fail closed or be normalized deterministically with explicit rationale.
- Affected files
  - `spectrum_systems/modules/runtime/evaluation_budget_governor.py`
  - `tests/test_evaluation_control_loop.py`

### P2 (High — weakens reliability, policy integrity, or trustworthiness)

- Finding
  - **Decision artifacts are non-deterministic across identical inputs due to UUID/time generation.**
  - `build_validation_budget_decision` and legacy decision path use `_new_id()` + current-time fields.
- Why it matters
  - Weakens reproducibility and forensic comparability; “same input + same policy” does not reproduce identical artifacts.
- Minimal fix
  - Use deterministic IDs (content hash seed) and/or separate volatile metadata from decision substance; add deterministic replay test.
- Affected files
  - `spectrum_systems/modules/runtime/evaluation_budget_governor.py`
  - `tests/test_evaluation_budget_governor.py`
  - `tests/test_evaluation_control_loop.py`

- Finding
  - **Legacy decision path can fail open on impossible-but-schema-valid windows (`total_runs=0`) due to `_safe_divide(...,0)->0.0`.**
  - If `total_failed_runs>0` and `total_runs=0`, failure-rate signals are suppressed.
- Why it matters
  - Contradictory data can degrade to healthier status than warranted instead of fail-closing.
- Minimal fix
  - Add semantic validity guard: reject/blocked when denominator-critical counters are inconsistent (e.g., failed runs with zero total runs).
- Affected files
  - `spectrum_systems/modules/runtime/evaluation_budget_governor.py`
  - `contracts/schemas/evaluation_monitor_summary.schema.json`
  - `tests/test_evaluation_budget_governor.py`

### P3 (Medium — hardening or coverage gap)

- Finding
  - **Fail-closed branch in control-loop builder for missing fields is effectively unreachable after schema validation.**
  - Code checks for missing `overall_status` / `aggregated_slis` after already raising on schema-invalid summaries.
- Why it matters
  - Gives a false sense of boundary hardening; public behavior for malformed summaries is exception-path only.
- Suggested fix
  - Remove unreachable branch or move semantic checks before/with validation to clarify true boundary guarantees.
- Affected files
  - `spectrum_systems/modules/runtime/evaluation_budget_governor.py`

- Finding
  - **Schema under-specification permits semantically invalid status/response/trigger combinations.**
  - Decision schema validates field-level enums but does not enforce semantic compatibility across `status`, `system_response`, and `triggered_thresholds`.
- Why it matters
  - “Schema-valid” is not equivalent to governance-valid.
- Suggested fix
  - Add cross-field constraints (or post-schema semantic validator) for allowed combinations.
- Affected files
  - `contracts/schemas/evaluation_budget_decision.schema.json`
  - `tests/test_evaluation_control_loop.py`

- Finding
  - **Coverage gaps for contradiction and reproducibility cases.**
  - No tests asserting rejection/escalation for contradictory status-vs-SLI summaries; no deterministic repeatability assertions for budget decisions.
- Why it matters
  - Critical integrity regressions can ship undetected.
- Suggested fix
  - Add targeted negative/consistency/replay tests (see section below).
- Affected files
  - `tests/test_evaluation_control_loop.py`
  - `tests/test_evaluation_budget_governor.py`

## Top 5 Immediate Fixes
1. Enforce semantic consistency gate in `build_validation_budget_decision` between `overall_status` and `aggregated_slis`; contradictory inputs must fail closed.
2. Disallow `healthy`/`allow` when any adverse trigger is emitted; add explicit invariant checks before artifact emission.
3. Introduce deterministic decision ID generation (input + policy hash) and deterministic replay tests.
4. Add semantic guard for `total_runs=0` contradiction cases in legacy path (`total_failed_runs>0`, critical alerts interplay).
5. Add cross-field semantic validation layer (schema or code) for status/response/trigger compatibility.

## Pass/Fail Against Invariants
- **Fail-Closed:** **PARTIAL** (schema-malformed inputs fail, but schema-valid contradictory summaries can yield governance-misleading outputs)
- **Schema Compliance:** **PASS** (produced artifacts are schema-valid)
- **Semantic Integrity:** **FAIL** (status/response can conflict with triggered evidence)
- **Determinism:** **FAIL** (UUID/time variability)
- **Policy Integrity:** **FAIL** (over-reliance on upstream status without evidence consistency checks)
- **Traceability:** **PARTIAL** (trace fields present, but non-deterministic IDs reduce reproducible trace linkage)
- **Single Source of Truth:** **PARTIAL** (schema authority is centralized, but schema does not encode required semantic invariants)

## Recommended Follow-Up Tests
1. Contradictory summary test: `overall_status="healthy"` with `output_paths_valid_rate<1.0` must not return `allow`.
2. Status/SLI coherence tests for each control-loop status bucket boundary (healthy/warning/exhausted/blocked).
3. Deterministic replay test: identical summary + thresholds produce identical decision substance and deterministic ID.
4. Legacy contradiction test: `total_runs=0` with nonzero failures/alerts fails closed.
5. Trigger/response invariant tests: adverse trigger sets cannot coexist with permissive responses.

## Gaps Not Covered
- Upstream monitor-record construction correctness beyond minimal boundary verification.
- Runtime deployment/operator policy outside repository-defined logic.
- Non-target modules and non-DECIDE schemas not required to assess DECIDE trustworthiness.

---

### Trustworthiness Answer
**Can the DECIDE layer be trusted to produce semantically correct, deterministic, fail-closed governance decisions from summaries and policy inputs?**

**No. Current result: FAIL.**
