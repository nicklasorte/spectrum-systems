# FPO — Control-Loop Promotion Certification Review

---

## 1. Review Metadata

| Field | Value |
|---|---|
| Review Date | 2026-03-27 |
| Review ID | FPO-CLT-PROMO-CERT-2026-03-27 |
| Repository | nicklasorte/spectrum-systems |
| Branch | claude/review-promotion-certification-re18K |
| Reviewer / Agent | Claude (reasoning agent — Sonnet 4.6) |
| Review Type | FPO — surgical promotion-gate / fail-closed certification review |
| Plan Reference | `docs/review-actions/PLAN-PQX-CLT-004-2026-03-27.md` |
| Action Tracker | `docs/review-actions/2026-03-27-control-loop-promotion-certification-review-actions.md` |

**Files reviewed (exact scope):**

- `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py`
- `scripts/run_evaluation_enforcement_bridge.py`
- `contracts/schemas/evaluation_enforcement_action.schema.json`
- `tests/test_evaluation_enforcement_bridge.py`
- `docs/runtime/control-loop-certification-pack.md`
- `docs/review-actions/PLAN-PQX-CLT-004-2026-03-27.md`
- `PLANS.md`

---

## 2. Scope

**In-bounds:** Promotion seam correctness; fail-closed certification behavior for missing, malformed, schema-invalid, uncertified, and fail-decision packs; bypass paths; governance output field completeness and schema alignment; CLI exit-code semantics; test sufficiency for negative certification cases; documentation accuracy for mandatory vs. advisory language.

**Out-of-bounds:** Control-loop certification pack generator (`run_control_loop_certification.py`); budget decision governor; override authorization flows (separately disabled); other modules not listed above.

---

## 3. Executive Summary

**Overall Verdict: CONDITIONAL PASS**

The certification gate is wired into the real promotion/governance seam. The fail-closed fundamentals are structurally sound: every blocking condition (missing, malformed, schema-invalid, uncertified, fail-decision) routes through `_evaluate_certification_gate()` and terminates in `gate_passed=False`, which then overrides `system_response` to `"block"` unconditionally in `enforce_budget_decision()`. No bypass flag, optional parameter, or exception fallthrough exists that allows promotion to proceed when the gate has not passed. Schema `additionalProperties: false` is enforced at both the root artifact and the nested `certification_gate` sub-object. Governance output fields (`artifact_reference`, `certification_decision`, `certification_status`, `block_reason`) are present and deterministic.

Two findings require remediation before this gate is fully verified. Both are in test coverage, not in runtime logic:

- **H-01 (test gap):** The file-not-found-with-explicit-path branch (`_evaluate_certification_gate()` lines 207–215) is fail-closed in code but has no test. This is an untested security-critical path.
- **H-02 (test gap):** The schema-invalid-certification-pack branch (lines 230–240) is fail-closed in code but has no test. A valid-JSON, schema-failing artifact hitting the gate is untested.

One additional finding creates operational risk through a documentation/runtime mismatch:

- **H-03 (doc/runtime mismatch):** The "Interpret exit code" table in `docs/runtime/control-loop-certification-pack.md` lists exit code `1` for "uncertified/fail", but the enforcement bridge CLI implements only exit codes 0 (allow/warn) and 2 (blocked/failure). There is no exit code 1 in the CLI. This is ambiguous at best and misleading at worst for operators scripting against this gate.

One medium finding creates a silently permissive API-layer path:

- **M-01:** `determine_enforcement_scope()` silently falls back to `"release"` on unknown scope. API callers (not CLI) supplying a misspelled or wrong scope will skip the certification gate without an error. The CLI mitigates this via `choices=`, but the programmatic seam does not.

---

## 4. Finding Detail

---

### Finding H-01 — Untested: file-not-found with explicit path provided

**Priority:** High
**File:** `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py` lines 205–215
**File:** `tests/test_evaluation_enforcement_bridge.py`

**Description:**
`_evaluate_certification_gate()` handles the case where a `control_loop_certification_path` is supplied in context but the file at that path does not exist. The handler correctly sets `gate_passed=False`, `certification_decision="missing"`, `certification_status="missing"`, and a specific `block_reason`. However, no test case exercises this path.

The existing test `test_promotion_missing_certification_blocks` exercises the path where no `control_loop_certification_path` key is provided at all — a different branch (the `if not path_value: return gate` branch at lines 202–203). The explicit-path-file-not-found branch at lines 207–215 is structurally fail-closed but entirely untested.

**Risk:** If a regression were introduced in this branch (e.g., a condition inversion or a path coercion bug), it would not be caught by the existing suite. For a security-critical gate, untested code paths cannot be considered verified.

---

### Finding H-02 — Untested: schema-invalid certification pack (valid JSON, schema violation)

**Priority:** High
**File:** `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py` lines 230–240
**File:** `tests/test_evaluation_enforcement_bridge.py`

**Description:**
`_evaluate_certification_gate()` validates the parsed certification pack against the `control_loop_certification_pack` JSON Schema. If validation fails, the handler correctly sets `gate_passed=False`, `certification_decision="malformed"`, `certification_status="malformed"`, and appends the schema error messages to `block_reason`.

The existing test `test_promotion_malformed_certification_blocks` only exercises the `json.JSONDecodeError` branch (unparseable JSON). It does not exercise the schema validation failure branch. A certification artifact that is syntactically valid JSON but schema-invalid (e.g., missing required fields, wrong enum value for `decision`) is handled by distinct code at lines 230–240 with no test coverage.

**Risk:** The schema validation branch is a defense-in-depth layer that verifies the artifact conforms to the governed contract before its field values are trusted. An untested schema-validation bypass risk is a meaningful gap for a certification gate.

---

### Finding H-03 — Documentation/runtime mismatch: exit code 1 does not exist

**Priority:** High
**File:** `docs/runtime/control-loop-certification-pack.md` lines 84–88
**File:** `scripts/run_evaluation_enforcement_bridge.py`

**Description:**
The "Interpret exit code" section in `docs/runtime/control-loop-certification-pack.md` reads:

```
- `0` = certified/pass
- `1` = uncertified/fail
- `2` = blocked
```

The enforcement bridge CLI (`scripts/run_evaluation_enforcement_bridge.py`) implements only two exit codes:
- `EXIT_ALLOW = 0` — allow or warn
- `EXIT_BLOCKED = 2` — freeze or block (and all error paths)

There is no exit code 1. Every non-allow state, including `uncertified/fail`, exits with code 2. The exit code table in the documentation is factually incorrect for the enforcement bridge CLI.

If this table was intended to describe `scripts/run_control_loop_certification.py` (the certification builder), that is not clear from context: the exit code table appears in the "Operational usage" section that shows both scripts. Any operator or CI pipeline scripting against this documentation expecting exit code 1 for uncertified/fail will receive exit code 2 instead and may handle it incorrectly.

**Risk:** Operator misconfiguration of CI integration. Downstream systems that treat exit 1 as a non-blocking warning and exit 2 as a hard failure would incorrectly classify a certification gate block as a hard failure regardless, but any system treating exit 1 as "no action needed" would fail open when the enforcement bridge actually returns exit 2. The ambiguity must be resolved.

---

### Finding M-01 — Unknown scope silently degrades to "release" at API layer

**Priority:** Medium
**File:** `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py` lines 539–550
**File:** `tests/test_evaluation_enforcement_bridge.py` line 275

**Description:**
`determine_enforcement_scope()` accepts a free-form `context["enforcement_scope"]` value. If the value is not in `valid_scopes`, it logs a warning and silently returns `_DEFAULT_SCOPE = "release"`. An API caller passing `context={"enforcement_scope": "promotoin"}` (typo) or any unrecognized scope would silently receive a "release"-scoped action without triggering the certification gate.

The CLI mitigates this via `choices=["promotion", "release", ...]` in the argparse definition — an invalid scope string at the CLI layer is rejected before the bridge is called. However, any caller using `enforce_budget_decision()` or `run_enforcement_bridge()` directly (e.g., in programmatic pipeline integration) would silently bypass the certification gate on scope typos or invalid values.

The test at line 275 (`test_determine_enforcement_scope_unknown_falls_back`) explicitly asserts this fallback behavior as correct, confirming it is intentional — but this does not eliminate the operational trust risk at the programmatic seam.

**Risk:** Implicit allow path at the API layer for any caller that supplies an unrecognized scope string. Scope validation at the API layer is advisory (log-only), not fail-closed.

---

### Finding M-02 — Stale test-list header comments

**Priority:** Medium
**File:** `tests/test_evaluation_enforcement_bridge.py` lines 32–36

**Description:**
The numbered comment block at the top of the test file includes entries that no longer match the implementation:

- Line 35: "CLI exit 1 — require_review (no override)" — Exit code 1 does not exist in the CLI.
- Line 36: "CLI exit 0 — require_review with override-authorization" — Overrides are explicitly blocked (`raise EnforcementBridgeError("override_authorization is not supported...")`). The actual test `test_cli_exit_2_override_not_supported` asserts exit 2, the opposite behavior.

These stale entries describe a legacy design that is no longer implemented. New contributors reading the test manifest will have incorrect expectations about what the CLI accepts and what exit codes are valid.

---

### Finding L-01 — No test verifying block_reason=None on certification pass

**Priority:** Low
**File:** `tests/test_evaluation_enforcement_bridge.py`

**Description:**
`test_promotion_certified_pass_allows` verifies `certification_status`, `certification_decision`, and `artifact_reference` for the pass case but does not assert that `block_reason` is `None`. The schema permits a non-null `block_reason` on pass, and the runtime sets it to `None` at line 264. A regression in that assignment would not be caught.

---

### Finding L-02 — No test for warn + promotion + certified/pass

**Priority:** Low
**File:** `tests/test_evaluation_enforcement_bridge.py`

**Description:**
All promotion certification tests use `_ALLOW` (a `system_response=allow` decision fixture) as the input. There is no test where a `warn` budget decision reaches the promotion certification gate with a certified/pass artifact. The certification gate overrides `system_response` to `"block"` when the gate fails, but when the gate passes, the original `system_response` must survive unchanged. Only `allow` is covered; `warn` is not.

---

### Finding L-03 — CLI `--control-loop-certification` not labeled required by argparse

**Priority:** Low
**File:** `scripts/run_evaluation_enforcement_bridge.py` lines 144–152

**Description:**
The `--control-loop-certification` argument help text reads "Required for fail-closed promotion gating in control-loop slice" but argparse treats it as optional (`default=None`, no `required=True`). The argument can be omitted without error at the CLI layer. Fail-closed behavior for the missing-certification case is enforced at the runtime bridge layer, not at CLI argument parsing. This is operationally acceptable but creates ambiguity: the help text says "required" while the CLI accepts its absence silently.

---

## 5. Verified Correct

The following aspects of the implementation were reviewed and found to be correct:

**Promotion seam:** The certification gate is wired directly into `enforce_budget_decision()` — the sole governed seam for all enforcement actions. There is no parallel or shadow promotion path. Non-promotion scopes receive `not_applicable` certification fields with `gate_passed=True` and are correctly unaffected.

**Blocking conditions — all verified fail-closed:**
- Missing path in context: `gate_passed=False`, `artifact_reference="missing"` ✓
- Path provided, file not found: `gate_passed=False` (code path exists, untested — see H-01) ✓
- Malformed JSON: `json.JSONDecodeError` caught, `gate_passed=False`, `certification_status="malformed"` ✓
- Schema-invalid: errors appended to `block_reason`, `gate_passed=False` (code path exists, untested — see H-02) ✓
- `certification_status != "certified"`: explicit check at line 248, `gate_passed=False` ✓
- `decision != "pass"`: explicit check at line 256, `gate_passed=False` ✓

**No bypasses:** No bypass flag, optional parameter, or weak default that silently allows promotion when certification fails. The `if not certification_gate["gate_passed"]` check at line 739 unconditionally overrides `system_response` to `"block"` before `allowed_to_proceed` is set.

**Override authorization blocked:** Any context containing `override_authorization` raises `EnforcementBridgeError` at line 735. Overrides cannot be used to circumvent the certification gate.

**Invariant enforcement:** `build_enforcement_action()` validates the `allowed_to_proceed` / `system_response` invariant (lines 641–647) and schema-validates the artifact before return. A malformed internal state cannot produce a passing action.

**Schema `additionalProperties: false`:** Applied at the root artifact and at the `certification_gate` sub-object in `evaluation_enforcement_action.schema.json`. No undeclared fields can be added by callers or the runtime without causing schema validation failure.

**Governance output completeness:** `certification_gate` carries `artifact_reference`, `certification_decision`, `certification_status`, and `block_reason` for all scopes. Values are deterministic: same inputs, same outputs. Block reasons are specific and operationally actionable.

**CLI fail-closed:** The `except Exception` catch-all at CLI lines 182–187 returns `EXIT_BLOCKED` for any unexpected failure. The secondary `not allowed_to_proceed` check at lines 238–244 catches any state where `action_type` is not freeze/block but the action is still non-proceeding. CLI input errors (invalid decision, bridge failure) all route to exit 2.

**Certification gate field values:** `certification_decision` enum (`pass`, `fail`, `blocked`, `missing`, `malformed`, `not_applicable`) and `certification_status` enum (`certified`, `uncertified`, `blocked`, `missing`, `malformed`, `not_applicable`) cover all runtime-producible values. Internally produced values match schema-allowed values.

**Determinism:** Confirmed by `test_promotion_missing_certification_is_deterministically_fail_closed` — same inputs produce identical `certification_gate` fields and `reasons` across two consecutive calls.

---

## 6. Next Steps

1. Add test for explicit-path-file-not-found case in `_evaluate_certification_gate()` — see H-01.
2. Add test for schema-invalid certification pack (valid JSON, fails schema validation) — see H-02.
3. Resolve the exit code 1 documentation discrepancy in `docs/runtime/control-loop-certification-pack.md` — either clarify which script the table describes, or correct it to match the enforcement bridge's 0/2 scheme — see H-03.
4. Harden `determine_enforcement_scope()` to raise on unrecognized scope at the API layer, or document the fallback behavior as an explicit design constraint — see M-01.
5. Update stale test-list header comments to reflect current behavior — see M-02.

---

## 7. Review Registry Entry

Register in `docs/reviews/review-registry.md` as:

| Review ID | Date | Type | Verdict | Plan |
|---|---|---|---|---|
| FPO-CLT-PROMO-CERT-2026-03-27 | 2026-03-27 | FPO surgical | CONDITIONAL PASS | PQX-CLT-004 |
