# Replay Governance Gate (BY)

## Purpose

This document describes the BY Replay Governance Gate: a control-plane
feature that promotes replay from an advisory monitoring signal into an
enforceable governance gate.

A replay result can now stop, quarantine, or force review of downstream
execution. Replay drift is no longer interesting telemetry. It is an
operational control.

---

## Why BX Was Not Enough

BX (the Replay Decision Integrity Engine, `replay_decision_engine.py`) evaluates
whether a replayed execution reproduces the same SLO decision as the original
run. It produces a `replay_decision_analysis` artifact containing:

- `decision_consistency.status` — consistent / drifted / indeterminate
- `reproducibility_score` — a float in [0, 1]
- `drift_type` — classification of detected drift

BX answers the question: *does this run reproduce?*

BX does not answer: *what should the system do about it?*

The analysis artifact from BX is produced as an observation. Nothing in BX
prevents a drifted run from continuing, publishing outputs, or being promoted
as a governed artifact. The signal was visible but non-enforceable.

BY closes that loop. It consumes the BX analysis artifact and emits an
enforceable `replay_governance_decision` artifact that:

1. Maps replay status + policy to one of four system responses: `allow`,
   `require_review`, `quarantine`, `block`.
2. Provides machine-readable rationale codes so enforcement is traceable.
3. Is wired into the control chain so responses are enforced, not just logged.

---

## Replay Governance Model

The governance gate evaluates the BX artifact against a `governance_policy`
and emits a `replay_governance_decision` artifact.

### Decision mapping

| Replay status      | Default action   | Override options   |
|--------------------|------------------|--------------------|
| `consistent`       | `allow`          | Not configurable   |
| `drifted`          | `quarantine`     | `block`            |
| `indeterminate`    | `require_review` | `block`            |
| Missing (optional) | `allow`          | `require_review`, `block` |
| Missing (required) | per policy       | `allow`, `require_review`, `block` |
| Malformed/invalid  | `block`          | Not configurable — fail closed |

**Fail closed rule:** malformed, missing-required-fields, unknown status, or
SLI-out-of-range replay artifacts always produce `block`. There is no
configuration to change this behaviour.

---

## Policy Model

A `governance_policy` object controls the configurable parts of the decision:

```json
{
  "policy_name": "default_replay_governance",
  "policy_version": "1.0.0",
  "drift_action": "quarantine",
  "indeterminate_action": "require_review",
  "missing_replay_action": "allow",
  "require_replay": false
}
```

| Field                   | Allowed values                      | Purpose |
|-------------------------|-------------------------------------|---------|
| `drift_action`          | `quarantine`, `block`               | Applied when replay is drifted |
| `indeterminate_action`  | `require_review`, `block`           | Applied when replay is indeterminate |
| `missing_replay_action` | `allow`, `require_review`, `block`  | Applied when replay is absent and required |
| `require_replay`        | `true`, `false`                     | If true, absence of replay triggers `missing_replay_action` |

The default policy is strict but not maximally restrictive:
- Drift → quarantine (not block), to allow investigation before hard stop.
- Indeterminate → require_review, not block, because indeterminate is not
  definitive evidence of failure.
- Missing + not required → allow, preserving backward compatibility.

---

## Enforcement Precedence

When the replay governance gate is wired into the control chain, its
`system_response` is merged with the existing control chain decision using
strict-precedence merging:

```
block > quarantine > require_review > allow
```

The `merge_system_responses(responses: list[str]) -> str` function implements
this. Unknown values are treated as `block` per fail-closed policy.

**Concrete consequence:**
- A control chain that would have continued (`allow`) is stopped if replay
  governance says `quarantine` or `block`.
- A control chain that was already blocked stays blocked regardless of the
  replay governance response.

---

## Failure Modes

### Malformed replay artifact
- The artifact fails `_validate_replay_analysis()`.
- `system_response` is forced to `block`.
- `rationale_code` is `replay_invalid_artifact`.
- Artifact `status` is `invalid_input`.
- This path cannot be configured away.

### Missing replay when not required
- `system_response` is `allow`.
- `decision.replay_governed` is `false`.
- `rationale_code` is `replay_not_required`.
- The governance gate is bypassed, not applied.

### Missing replay when required
- `require_replay=true` (caller or policy).
- `system_response` is `policy.missing_replay_action`.
- `rationale_code` is `replay_missing_required`.
- This is the configurable path for mandatory replay policies.

### Unknown replay status
- `decision_consistency.status` is not `consistent`, `drifted`, or
  `indeterminate`.
- Forces `block` with `rationale_code=replay_unknown_status`.
- This path is hit even if the status was once valid but has been changed
  by a future schema version the current gate does not recognise.

### Conflicting responses
- `merge_system_responses` always returns the strictest response.
- Any `block` in the list returns `block`.
- Any unrecognised value in the list returns `block`.

---

## Example Artifacts

### Drifted replay under default policy

```json
{
  "artifact_type": "replay_governance_decision",
  "schema_version": "1.0.0",
  "replay_analysis_artifact_id": "replay-analysis-123",
  "run_id": "run-123",
  "evaluated_at": "2026-03-20T12:00:00+00:00",
  "replay_status": "drifted",
  "replay_consistency_sli": 0.0,
  "governance_policy": {
    "policy_name": "default_replay_governance",
    "policy_version": "1.0.0",
    "drift_action": "quarantine",
    "indeterminate_action": "require_review",
    "missing_replay_action": "allow",
    "require_replay": false
  },
  "decision": {
    "system_response": "quarantine",
    "severity": "elevated",
    "replay_governed": true,
    "rationale_code": "replay_drifted",
    "rationale": "Replay drift was detected. Governed outputs cannot be promoted automatically."
  },
  "enforcement_reason": {
    "summary": "Replay governance escalated the run to quarantine.",
    "details": [
      "replay_status=drifted",
      "replay_consistency_sli=0.0",
      "policy.drift_action=quarantine"
    ]
  },
  "status": "policy_blocked"
}
```

### Consistent replay

```json
{
  "artifact_type": "replay_governance_decision",
  "schema_version": "1.0.0",
  "replay_analysis_artifact_id": "replay-analysis-456",
  "run_id": "run-456",
  "evaluated_at": "2026-03-20T12:00:00+00:00",
  "replay_status": "consistent",
  "replay_consistency_sli": 1.0,
  "governance_policy": { "...": "..." },
  "decision": {
    "system_response": "allow",
    "severity": "info",
    "replay_governed": true,
    "rationale_code": "replay_consistent",
    "rationale": "Replay is consistent with the original execution. Governed outputs may proceed."
  },
  "enforcement_reason": {
    "summary": "Replay governance: execution allowed; replay is consistent.",
    "details": ["replay_status=consistent", "replay_consistency_sli=1.0"]
  },
  "status": "ok"
}
```

---

## How This Advances Spectrum Maturity

Before BY:
- BX produced a `replay_decision_analysis` artifact.
- The drift signal was observable but not operational.
- Nothing in the pipeline enforced a response to drift.
- Replay was monitoring-only, not governance.

After BY:
- Replay drift is an operational control signal.
- The control chain (`run_control_chain`) accepts a `replay_governance_decision`
  artifact and merges its `system_response` into the final continuation decision.
- `block` and `quarantine` and `require_review` are enforced, not just logged.
- All governance decisions are schema-validated, machine-readable artifacts with
  explicit rationale codes.
- The system can be operated with different strictness levels by changing the
  policy, without changing code.
- Malformed replay inputs fail closed — they cannot silently pass.

This aligns with the Spectrum SRE principle that artifact validity, traceability,
and explainability must be first-class service attributes with SLOs and error
budgets governing change, not just dashboards.

---

## Files

| File | Purpose |
|------|---------|
| `contracts/schemas/replay_governance_decision.schema.json` | JSON Schema 2020-12 for the governance decision artifact |
| `spectrum_systems/modules/runtime/replay_governance.py` | BY runtime module with deterministic fail-closed logic |
| `spectrum_systems/modules/runtime/control_chain.py` | Updated to wire replay governance into the enforcement path |
| `tests/test_replay_governance.py` | Comprehensive test suite proving fail-closed behaviour |
| `docs/design/replay-governance.md` | This document |
