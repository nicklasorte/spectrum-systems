# 3LS Authority Boundary Firewall — Red-Team Review

**Reviewer:** ARA-3LS-01
**Reviewed batch:** 3LS-01 (3LS Authority Boundary Firewall + preflight repair suggestions)
**Date:** 2026-04-25
**Decision:** revise (one S3 finding, fixed in this same batch)

## Scope of the review

This review red-teamed the authority boundary firewall against the failure modes
called out in the batch instructions:

- authority leak in TLC
- authority leak in PQX
- authority leak in dashboard / API surface
- attempt to silence a leak via fake allowlist
- missing neutral vocabulary map
- scan failure
- attempt to mark a finding S4 + non-blocking to slip past the gate

## Method

Each scenario was exercised either as an automated test
(`tests/governance/test_3ls_authority_preflight.py`,
`tests/governance/test_3ls_authority_repair_suggestions.py`) or as a manual
inspection of the registry, scripts, and tests.

## Findings

### F-001 — TLC non-owner authority leak

- **Scenario:** Add `payload = {'decision': 'allow'}` to a file under
  `spectrum_systems/modules/orchestration/`.
- **Result:** Preflight fails. Forbidden field `decision` and forbidden value
  `allow` both surface as violations. Suggested repair offers
  `gate_evidence` / `routing_result` and `passed_gate` / `gate_evidence_valid`.
- **Severity:** S0 (covered, no defect).

### F-002 — PQX non-owner authority leak

- **Scenario:** Add `payload = {'decision': 'block'}` to a file under
  `spectrum_systems/modules/orchestration/`.
- **Result:** Preflight fails. `block` is flagged with neutral suggestion
  `failed_gate` / `gate_evidence_invalid`.
- **Severity:** S0 (covered, no defect).

### F-003 — Dashboard / API authority leak coverage gap

- **Scenario:** A file under `dashboard/`, `app/`, or `components/` emits
  `decision: allow`.
- **Result:** Neither the existing CI guard nor the new preflight catches it,
  because `default_scope_prefixes` in `authority_registry.json` only covers
  `spectrum_systems/modules/` and `contracts/examples/`.
- **Severity:** S3 (known gap).
- **Resolution in this batch:** DASHBOARD is recorded in
  `three_letter_system_authority` with empty `owner_path_prefixes` and an
  explicit `scope_note` documenting the limitation. A future scope extension
  is now a tractable change with a named target. See fix actions
  (`contracts/review_actions/3LS_authority_firewall_fix_actions.json`,
  `FIX-001`).
- **Why not raised to S2:** The existing CI gate has always had this scope.
  Extending the scope would impact existing dashboard files using the words
  `allow` / `block` in unrelated contexts (CSS classes, button labels), which
  is out of scope for this batch and would require a separate review.

### F-004 — Fake allowlist override attempt

- **Scenario:** Adversary proposes adding a non-owner path to
  `vocabulary_overrides.allowed_values` to silence a leak.
- **Result:** The repair suggester never proposes allowlist overrides for
  non-owner files; instead it suggests neutral vocabulary or restructuring.
  For owner-path files, the suggester flags
  `owner_authority_review_required: true` rather than auto-widening overrides.
  `tests/governance/test_3ls_authority_repair_suggestions.py::
  test_suggested_repairs_no_allowlist_override_for_non_owner` and
  `test_owner_path_violation_requires_manual_review` cover this.
- **Severity:** S0 (covered, no defect).

### F-005 — Missing neutral vocabulary map

- **Scenario:** Delete `contracts/governance/authority_neutral_vocabulary.json`
  and run the preflight.
- **Result:** Preflight raises `ThreeLetterAuthorityPreflightError` and exits
  non-zero. `tests/governance/test_3ls_authority_preflight.py::
  test_missing_neutral_vocabulary_fails_closed` and
  `test_neutral_vocabulary_wrong_artifact_type_fails_closed` cover this.
- **Severity:** S0 (covered, no defect).

### F-006 — Scan failure

- **Scenario:** Provide a malformed JSON or syntactically broken Python file in
  the changed-file set.
- **Result:** The preflight wraps detector errors in
  `ThreeLetterAuthorityPreflightError` with the offending file path included,
  and exits non-zero. The CI guard at `scripts/run_authority_leak_guard.py`
  uses the same fail-closed pattern.
- **Severity:** S0 (covered, no defect).

### F-007 — S4 + blocking=false bypass attempt

- **Scenario:** A review artifact carrying authority vocabulary attempts to
  smuggle the leak past the guard by tagging itself
  `severity: S4, blocking: false`.
- **Result:** The preflight ignores the severity / blocking metadata; the
  vocabulary and shape detection fire on the artifact's content. Test
  `test_s4_non_blocking_review_artifact_still_fails` verifies this.
- **Severity:** S0 (covered, no defect).

### F-008 — Existing CI guard non-weakening

- **Scenario:** Confirm the existing `scripts/run_authority_leak_guard.py`
  still fails on a non-owner `decision: allow` after registry changes.
- **Result:** All 11 existing authority-leak tests pass. Test
  `test_existing_authority_leak_guard_still_catches_forbidden_value` re-exercises
  the CI guard as part of this batch.
- **Severity:** S0 (covered, no defect).

## Summary

- 1 S3 finding (F-003), resolved in-batch with explicit registry annotation
  and a tractable scope-extension path. Regression test
  (`test_classify_three_letter_system_owner_match` plus DASHBOARD coverage
  in the registry classification helper) confirms the registry entry is
  visible to the firewall.
- No S2+ findings.
- Existing CI guard unweakened.
- No broad allowlists added.
- Suggester never proposes silencing non-owner leaks via overrides.
