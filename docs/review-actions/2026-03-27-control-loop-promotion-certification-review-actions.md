# Control-Loop Promotion Certification Review — Action Tracker

- **Source Review:** `docs/reviews/2026-03-27-control-loop-promotion-certification-review.md`
- **Review ID:** FPO-CLT-PROMO-CERT-2026-03-27
- **Plan:** `docs/review-actions/PLAN-PQX-CLT-004-2026-03-27.md`
- **Owner:** Runtime Governance Working Group
- **Last Updated:** 2026-03-27

---

## Closure Note

This tracker is formally closed by `docs/reviews/2026-03-27-control-loop-promotion-certification-closure.md` after completion of the PQX-CLT-005 through PQX-CLT-008 remediation chain.

---

## Critical Items

None. The runtime fail-closed logic is structurally correct. No critical defects were identified.

---

## High-Priority Items

| ID | Action Item | File(s) | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| H-01 | Add test for `_evaluate_certification_gate()` path where a `control_loop_certification_path` is supplied in context but the referenced file does not exist on disk. Assert `allowed_to_proceed=False`, `action_type="block"`, `certification_status="missing"`, `certification_decision="missing"`, and that `block_reason` is non-null. | `tests/test_evaluation_enforcement_bridge.py` | Runtime QA | Resolved | None | Resolved by PQX-CLT-005 fail-closed negative-path coverage additions. |
| H-02 | Add test for `_evaluate_certification_gate()` path where a certification artifact is valid JSON but fails the `control_loop_certification_pack` JSON Schema (e.g., missing required fields, invalid enum value). Assert `allowed_to_proceed=False`, `action_type="block"`, `certification_status="malformed"`, `certification_decision="malformed"`, and that `block_reason` references the schema error. | `tests/test_evaluation_enforcement_bridge.py` | Runtime QA | Resolved | None | Resolved by PQX-CLT-005 schema-invalid certification-pack coverage. |
| H-03 | Resolve the exit code table discrepancy in `docs/runtime/control-loop-certification-pack.md` lines 84–88. The table lists exit code `1` for "uncertified/fail" but the enforcement bridge CLI (`scripts/run_evaluation_enforcement_bridge.py`) implements only exit 0 and exit 2. Either: (a) correct the table to match the enforcement bridge (0=allow/warn, 2=all blocked/failed states), or (b) clearly annotate that the table describes `run_control_loop_certification.py` only and add a separate accurate table for the enforcement bridge. | `docs/runtime/control-loop-certification-pack.md` | Documentation Owner | Resolved | None | Resolved by PQX-CLT-006 operator contract alignment across docs and CLI help semantics. |

---

## Medium-Priority Items

| ID | Action Item | File(s) | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| M-01 | Harden `determine_enforcement_scope()` at the API layer to raise `EnforcementBridgeError` on unrecognized scope values rather than silently falling back to `"release"`. CLI callers are already protected by argparse `choices=`, but programmatic callers using `enforce_budget_decision()` directly are not. Alternatively, document the silent-fallback behavior explicitly as a stable design constraint and add a test asserting that promotion-specific callers always provide a validated scope. | `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py` | Runtime Governance | Resolved | None | Resolved by PQX-CLT-007 fail-closed scope handling for invalid API-layer scope values. |
| M-02 | Update the numbered test-list comment block at the top of `tests/test_evaluation_enforcement_bridge.py` (lines 32–36). Remove or correct entries referencing exit code 1 (does not exist in CLI) and CLI exit 0 for override-authorization (overrides are blocked and return exit 2). Ensure the manifest accurately reflects current test behavior to prevent contributor confusion. | `tests/test_evaluation_enforcement_bridge.py` | Runtime QA | Resolved | None | Resolved by PQX-CLT-006/PQX-CLT-008 test-manifest wording and behavior alignment. |

---

## Low-Priority Items

| ID | Action Item | File(s) | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| L-01 | Add assertion in `test_promotion_certified_pass_allows` (or a dedicated test) that `action["certification_gate"]["block_reason"]` is `None` when certification passes. | `tests/test_evaluation_enforcement_bridge.py` | Runtime QA | Resolved | None | Resolved by PQX-CLT-008 pass-path hardening assertions. |
| L-02 | Add a test variant of the certified/pass promotion path using a `warn` budget decision input (not only `allow`). Assert that a `warn` decision + promotion scope + certified/pass artifact produces `action_type="warn"`, `allowed_to_proceed=True`, and correct certification fields. | `tests/test_evaluation_enforcement_bridge.py` | Runtime QA | Resolved | None | Resolved by PQX-CLT-008 warn-preservation promotion test coverage. |
| L-03 | Clarify or remove the "Required for fail-closed promotion gating" language in the `--control-loop-certification` argparse help text. The argument is not `required=True` in argparse; fail-closed enforcement happens at the runtime bridge layer, not the CLI parser. The current help text implies the CLI itself enforces the requirement, which is not accurate. | `scripts/run_evaluation_enforcement_bridge.py` | CLI Owner | Resolved | None | Resolved by PQX-CLT-006 wording update: parse-optional argument with explicit runtime fail-closed enforcement note. |

---

## Blocking Items

- None. Items H-01, H-02, and H-03 were completed in the PQX-CLT-005 through PQX-CLT-008 chain, and this review is closed via the linked closure artifact.

## Deferred Items

- None.
