# TPA Trust Boundary Verification — 2026-04-05

## Review Metadata
- review date: 2026-04-05
- scope: Targeted verification of TPA-09A fixes for (1) override expiration semantics and (2) repeated hardening escalation dampening only.
- files/surfaces inspected:
  - `contracts/schemas/hitl_override_decision.schema.json`
  - `contracts/examples/hitl_override_decision.json`
  - `spectrum_systems/modules/runtime/agent_golden_path.py`
  - `spectrum_systems/modules/runtime/tpa_complexity_governance.py`
  - `spectrum_systems/modules/runtime/pqx_sequence_runner.py`
  - `tests/test_agent_golden_path.py`
  - `tests/test_hitl_override_enforcement.py`
  - `tests/test_tpa_complexity_governance.py`
- reviewer = Codex

## 1. Override Expiration Assessment
**Status: Pass (with one caveat)**

### What is correct
- Canonical override contract now requires explicit expiration semantics:
  - `issued_at`, `expires_at`, and `max_validity_seconds` are required.
  - `max_validity_seconds` is bounded (`1..86400`).
- Canonical example is aligned to schema v1.1.0 and includes required expiry fields.
- Expiry is enforced at the real AG-04 runtime boundary, not only recorded:
  - enforcement path validates schema before use.
  - enforcement path validates expiry window and fails closed when invalid/expired.
- Expired overrides fail closed deterministically (`hitl_override_enforcement_failed`, blocked execution).
- Missing or malformed expiry semantics fail closed:
  - missing required expiry field fails schema validation.
  - invalid validity window / over-policy max fails before continuation.
- Override scope remains bounded:
  - decision scope must be `ag_runtime_review_boundary`.
  - trace ID, review request ID, and execution record ID must all match emitted boundary artifacts.
  - multiple override artifacts are rejected as ambiguous and blocked.

### What remains risky
- `issued_at` is validated for format and used for window math, but there is no explicit `enforcement_now >= issued_at` guard.
  - This does **not** create persistence drift, but it allows a “future-issued” override to be consumed early if all other checks pass.
  - This is a narrow temporal-validity caveat, not a bypass of expiration or scope checks.

### Concrete evidence
- Schema-required expiry fields and max TTL bound are present in the canonical contract.
- Runtime enforcement calls schema validation and explicit expiry-window enforcement in AG-04 override resolution.
- Fail-closed behavior is exercised by targeted tests for expired override, missing expiry, malformed override, incompatible override, and ambiguous override count.

## 2. Escalation Dampening Assessment
**Status: Conditional**

### What is correct
- Repeated hardening escalation cannot proceed on TPA-local signals alone:
  - repeated escalation is detected from prior mode + requested stronger mode.
  - when drivers are all `tpa_local:*` and no non-TPA corroboration is present, escalation is deterministically dampened.
- Corroboration requirement is explicit in output fields:
  - `corroboration_required_for_repeated_hardening`
  - `non_tpa_corroboration_refs`
- Repeated escalation without corroboration is blocked/downgraded deterministically:
  - mode and effective decision are reverted to prior values.
  - explicit reason codes emitted:
    - `repeated_tpa_local_escalation_blocked`
    - `corroboration_missing_for_repeated_hardening`
- Traceability exists via reason codes + corroboration refs in the returned control-priority signal.
- Determinism is preserved (sorting/canonicalization + replay tests asserting same inputs => same outputs).
- In authoritative TPA runner wiring, driver sources are hardcoded as TPA-local signals; this prevents accidental mixed-source self-escalation through that path.

### What remains risky
- Corroboration acceptance is currently **syntactic**, not semantic:
  - non-TPA corroboration is accepted based on ref prefix not starting with `tpa_`.
  - there is no local proof here that a referenced non-TPA artifact actually exists/validated at this decision point.
- Result: dampening is materially improved, but there is still a narrow spoofability gap if upstream surfaces can inject arbitrary corroboration-looking refs.

### Concrete evidence
- Dampening rule and reason-code emission are implemented directly in `build_control_priority_signal`.
- TPA runner passes hardcoded TPA-local driver sources and a corroboration-ref list into that function.
- Tests cover:
  - first hardening escalation allowed,
  - repeated TPA-local escalation blocked without non-TPA corroboration,
  - repeated escalation allowed with non-TPA corroboration,
  - deterministic replay behavior.

## 3. Remaining Risks
1. **Temporal caveat on override issuance bound (narrow):** no explicit not-before check (`enforcement_now >= issued_at`) in AG-04 override enforcement.
2. **Corroboration spoofability caveat (high priority within this scope):** repeated-escalation dampening treats non-TPA corroboration as prefix-based reference strings without explicit existence/validation proof at decision time.

## 4. Verdict
**Conditional**

TPA-09A materially fixed both priority trust-boundary issues, but not completely. Override expiration is effectively fail-closed at enforcement with one temporal caveat; escalation dampening is strong but corroboration trust is still too string-prefix-based to call fully closed.

## 5. Recommended Follow-Up
1. Add explicit `issued_at <= enforcement_now` check in AG-04 override enforcement.
2. Tighten corroboration gate so repeated hardening escalation requires at least one validated, resolvable non-TPA artifact reference (not just non-`tpa_` prefix text).
