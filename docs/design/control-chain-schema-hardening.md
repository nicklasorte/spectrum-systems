# Control Chain Schema Hardening (BZ)

## Purpose

Prompt BZ formally closes the remaining control-plane contract gap introduced by BY (Replay Governance Gate).
BY added runtime replay governance behavior to the control chain decision path, but the governing schema
for `slo_control_chain_decision` did not declare those fields.
This document records what BZ changed and why.

---

## Problem Fixed

BY wired replay governance into the control chain execution path and propagated its output fields into
the `slo_control_chain_decision` artifact.  However, those fields were set as **ad-hoc flat top-level
keys** that were not declared in the schema:

| Old ad-hoc field (removed) | Where it lived |
|---|---|
| `replay_governance_response` | top-level key on the artifact |
| `replay_governance_rationale_code` | top-level key |
| `replay_status` | top-level key |
| `replay_consistency_sli` | top-level key |
| `replay_governance_escalated_final_decision` | top-level key |

Because the schema had `additionalProperties: false`, these fields were silently violating the
contract every time replay governance was active.  Downstream consumers relying on those keys had
no schema guarantee, and drift or misspellings would pass unnoticed.

---

## Final Replay Governance Schema Shape

Replay governance is represented as a **nested object** under the key `replay_governance` on the
`slo_control_chain_decision` artifact.

```json
"replay_governance": {
  "type": "object",
  "additionalProperties": false,
  "required": ["present", "replay_governed"],
  "properties": {
    "present":                { "type": "boolean" },
    "replay_governed":        { "type": "boolean" },
    "replay_status":          { "type": "string", "enum": ["consistent","drifted","indeterminate"] },
    "replay_consistency_sli": { "type": "number", "minimum": 0, "maximum": 1 },
    "system_response":        { "type": "string", "enum": ["allow","require_review","quarantine","block"] },
    "severity":               { "type": "string", "enum": ["info","warning","elevated","critical"] },
    "rationale_code":         { "type": "string", "enum": ["replay_consistent","replay_drifted","replay_indeterminate","replay_missing_required","replay_invalid_artifact","replay_unknown_status","replay_not_required"] },
    "status":                 { "type": "string", "enum": ["ok","invalid_input","policy_blocked"] },
    "escalated_final_decision": { "type": "boolean" }
  },
  "if":   { "properties": { "present": {"const": true}, "replay_governed": {"const": true} } },
  "then": { "required": ["replay_status","replay_consistency_sli","system_response","severity","rationale_code","status"] }
}
```

The `blocking_layer` enum was also extended to include `"replay_governance"` as a valid value.

---

## Compatibility Strategy

**Option A — Additive minor schema evolution.**

- `replay_governance` is an **optional** property on the artifact.
- Artifacts produced before BZ (no `replay_governance` key) remain fully valid.
- New artifacts produced when replay governance is active **must** include the nested object in the declared shape.
- The field is intentionally absent when no replay governance artifact was supplied to the control chain.

This was chosen because the schema was not yet in a state that required a version bump — the new
field is purely additive.  The `schema_version` value (`1.0.0`) is unchanged.

---

## Validation Guarantees

After BZ, the `slo_control_chain_decision` artifact now rejects the following at schema-validation time:

| Invalid condition | Rejection mechanism |
|---|---|
| Flat `replay_governance_response` key at top level | `additionalProperties: false` |
| Flat `replay_status` key at top level | `additionalProperties: false` |
| Misspelled field inside `replay_governance` | `additionalProperties: false` on nested object |
| Unknown extra field inside `replay_governance` | `additionalProperties: false` on nested object |
| `replay_consistency_sli` outside [0, 1] | `minimum`/`maximum` constraints |
| Unknown `replay_status` value | `enum` constraint |
| Unknown `system_response` value | `enum` constraint |
| `present=true` + `replay_governed=true` but missing `replay_status` | `if/then` conditional |
| `present=true` + `replay_governed=true` but missing `system_response` | `if/then` conditional |
| `present=true` + `replay_governed=true` but missing `severity` | `if/then` conditional |
| `present=true` + `replay_governed=true` but missing `rationale_code` | `if/then` conditional |
| `present=true` + `replay_governed=true` but missing `status` | `if/then` conditional |

---

## Failure Cases Now Caught

- A producer that misspells `system_response` as `system_resonse` → schema error.
- A producer that adds an undeclared debug key to the replay governance block → schema error.
- A producer that emits `replay_consistency_sli: 1.5` → schema error.
- A producer that emits `replay_status: "unknown_state"` → schema error.
- A consumer that tries to read `artifact["replay_governance_response"]` → key absent, null return or KeyError depending on read style, not a silent wrong value.

---

## Why This Closes the Remaining BY Gap

BY made replay governance functionally wired but contractually informal.  The control chain
artifact had `additionalProperties: false` in the schema, but the ad-hoc flat fields silently
violated that constraint (they were set after schema validation had already run).

BZ ensures:
1. **Schema-first**: the nested `replay_governance` object is declared in `$defs` and referenced from `properties` before any code runs.
2. **Producer discipline**: the code that emits replay governance now builds the nested object from declared field names only.
3. **No undeclared extras**: the five old flat keys are gone from the artifact.
4. **Fail-closed schema**: `additionalProperties: false` now genuinely enforces the replay governance contract, not just the base fields.
5. **Negative test coverage**: tests prove misspellings, extra keys, out-of-range SLIs, and missing required-when-governed fields all fail validation.

---

## Files Changed

| File | Change |
|---|---|
| `contracts/schemas/slo_control_chain_decision.schema.json` | Added `replay_governance` to `$defs` and `properties`; added `replay_governance` to `blocking_layer` enum |
| `spectrum_systems/modules/runtime/control_chain.py` | Replaced five ad-hoc flat key assignments with a single nested `replay_governance` object build |
| `tests/test_replay_governance.py` | Updated `test_governance_fields_visible_in_result` to check the new nested shape |
| `tests/test_control_chain_schema_hardening.py` | New: 30 BZ tests covering schema, producer, consumer, and backward compatibility |
| `docs/design/control-chain-schema-hardening.md` | This document |
