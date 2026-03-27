# Control-Loop Promotion Certification Review — Action Tracker

- **Source Review:** `docs/reviews/2026-03-27-control-loop-promotion-certification-review.md`
- **Review ID:** FPO-CLT-PROMO-CERT-2026-03-27
- **Plan:** `docs/review-actions/PLAN-PQX-CLT-004-2026-03-27.md`
- **Owner:** Runtime Governance Working Group
- **Last Updated:** 2026-03-27

---

## Critical Items

None. The runtime fail-closed logic is structurally correct. No critical defects were identified.

---

## High-Priority Items

| ID | Action Item | File(s) | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| H-01 | Add test for `_evaluate_certification_gate()` path where a `control_loop_certification_path` is supplied in context but the referenced file does not exist on disk. Assert `allowed_to_proceed=False`, `action_type="block"`, `certification_status="missing"`, `certification_decision="missing"`, and that `block_reason` is non-null. | `tests/test_evaluation_enforcement_bridge.py` | Runtime QA | Open | None | Code path at lines 207–215 is fail-closed but untested. Distinct from the no-path case already covered by `test_promotion_missing_certification_blocks`. |
| H-02 | Add test for `_evaluate_certification_gate()` path where a certification artifact is valid JSON but fails the `control_loop_certification_pack` JSON Schema (e.g., missing required fields, invalid enum value). Assert `allowed_to_proceed=False`, `action_type="block"`, `certification_status="malformed"`, `certification_decision="malformed"`, and that `block_reason` references the schema error. | `tests/test_evaluation_enforcement_bridge.py` | Runtime QA | Open | None | Code path at lines 230–240 is fail-closed but untested. Distinct from the malformed-JSON case covered by `test_promotion_malformed_certification_blocks`. |
| H-03 | Resolve the exit code table discrepancy in `docs/runtime/control-loop-certification-pack.md` lines 84–88. The table lists exit code `1` for "uncertified/fail" but the enforcement bridge CLI (`scripts/run_evaluation_enforcement_bridge.py`) implements only exit 0 and exit 2. Either: (a) correct the table to match the enforcement bridge (0=allow/warn, 2=all blocked/failed states), or (b) clearly annotate that the table describes `run_control_loop_certification.py` only and add a separate accurate table for the enforcement bridge. | `docs/runtime/control-loop-certification-pack.md` | Documentation Owner | Open | None | Ambiguous whether exit code 1 refers to the certification builder or the enforcement bridge. Operators scripting against this documentation will receive exit 2 instead of exit 1 for uncertified/fail states. |

---

## Medium-Priority Items

| ID | Action Item | File(s) | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| M-01 | Harden `determine_enforcement_scope()` at the API layer to raise `EnforcementBridgeError` on unrecognized scope values rather than silently falling back to `"release"`. CLI callers are already protected by argparse `choices=`, but programmatic callers using `enforce_budget_decision()` directly are not. Alternatively, document the silent-fallback behavior explicitly as a stable design constraint and add a test asserting that promotion-specific callers always provide a validated scope. | `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py` | Runtime Governance | Open | None | The fallback is intentional per current tests but creates an implicit allow path at the API layer for scope typos or integration errors. |
| M-02 | Update the numbered test-list comment block at the top of `tests/test_evaluation_enforcement_bridge.py` (lines 32–36). Remove or correct entries referencing exit code 1 (does not exist in CLI) and CLI exit 0 for override-authorization (overrides are blocked and return exit 2). Ensure the manifest accurately reflects current test behavior to prevent contributor confusion. | `tests/test_evaluation_enforcement_bridge.py` | Runtime QA | Open | None | Stale entries describe a legacy design. |

---

## Low-Priority Items

| ID | Action Item | File(s) | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| L-01 | Add assertion in `test_promotion_certified_pass_allows` (or a dedicated test) that `action["certification_gate"]["block_reason"]` is `None` when certification passes. | `tests/test_evaluation_enforcement_bridge.py` | Runtime QA | Open | None | Prevents regression if the `None` assignment at line 264 is accidentally removed. |
| L-02 | Add a test variant of the certified/pass promotion path using a `warn` budget decision input (not only `allow`). Assert that a `warn` decision + promotion scope + certified/pass artifact produces `action_type="warn"`, `allowed_to_proceed=True`, and correct certification fields. | `tests/test_evaluation_enforcement_bridge.py` | Runtime QA | Open | None | Verifies the certification gate does not corrupt the original system_response on pass for non-allow advisory decisions. |
| L-03 | Clarify or remove the "Required for fail-closed promotion gating" language in the `--control-loop-certification` argparse help text. The argument is not `required=True` in argparse; fail-closed enforcement happens at the runtime bridge layer, not the CLI parser. The current help text implies the CLI itself enforces the requirement, which is not accurate. | `scripts/run_evaluation_enforcement_bridge.py` | CLI Owner | Open | None | Minor operator-clarity issue; does not affect runtime correctness. |

---

## Blocking Items

- H-01 and H-02 must be resolved before the PQX-CLT-004 certification gate can be considered fully verified. Untested fail-closed paths are unverified guarantees.
- H-03 must be resolved before this gate is documented as operationally ready for CI integration.

## Deferred Items

- None.
