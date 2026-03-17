# Validation and Failure Model

## Overview

The validation module (`spectrum_systems/modules/validation.py`) provides
structured validation of all artifacts produced by the meeting-minutes pipeline.
It produces `ValidationResult` objects and always writes `validation_report.json`
to the artifact package directory.

---

## Failure Categories

| Category | Description |
|---|---|
| `input_error` | Normalized case input is malformed or missing |
| `extraction_error` | `structured_extraction` is missing required keys/items |
| `signal_error` | `signals.json` is missing required keys/items |
| `study_state_error` | `study_state.json` fails propagation or schema checks |
| `schema_error` | A required key exists but has an unexpected type or value |
| `packaging_error` | Artifact package is missing one or more required files |
| `validation_error` | The validator itself encountered an unexpected problem |

## Severity Levels

| Level | Meaning |
|---|---|
| `error` | Hard failure; run result is invalid |
| `warning` | Degraded output; run may still be usable |
| `info` | Informational; no action required |

## Status Values

| Status | Condition |
|---|---|
| `pass` | No errors, no warnings |
| `pass_with_warnings` | Warnings present but no errors |
| `fail` | One or more errors |

---

## External Contract vs Internal Normalized Model

The validation system operates across two distinct representations of
meeting-minutes data.  Understanding the boundary between them is essential
for maintaining contract compliance and internal reasoning.

### External Contract (`contracts/`)

The authoritative external contract is defined in:

- `contracts/meeting_minutes_contract.yaml` — canonical field definitions
- `contracts/meeting-minutes.schema.json` — JSON Schema for strict validation
- `contracts/examples/meeting_minutes_contract.json` — governed example

The contract defines the **wire format** for data produced by and exchanged
between systems.  Key contract-format fields include:

**Extraction (structured_extraction.json):**
- `decisions_made` — array of decision objects with `decision_id`, `decision`,
  `rationale`, `decision_owner`, `agenda_item`, `date_made`, `revisit_trigger`
- `action_items` — array with `action_id`, `task`, `owner`, `due_date`,
  `dependencies`, `status`
- `discussion_questions_log` — optional, items with `category`, `question`,
  `asked_by`, `response`, `follow_up`, `source_reference`
- `risks_or_open_questions` — optional, items with `issue_id`, `description`,
  `impact`, `owner`, `target_resolution_date`

**Signals (signals.json):**
- Legacy format: `risks_or_open_questions`, `decisions_made`
- Normalized format: `questions`, `assumptions`, `risks`

The validator accepts both formats.  At least one valid representation must be
present.  Do **not** rewrite contracts to match the internal model.

### Internal Normalized Model (`study_state.json`)

The internal model is defined in `docs/architecture/study_state_model.md`.
It is the **reasoning model** used during study progression.

Key internal model fields:
- `decisions` — resolved commitments (id, decision, rationale, …)
- `action_items` — discrete tasks (id, task, owner, due_date, status, …)
- `questions` — open unresolved questions (id, question, raised_by, …)
- `assumptions` — explicit/implicit assumptions (id, assumption, basis, …)
- `risks` — tracked risks (id, description, impact, …)

The internal model uses consistent `id` keys across all item types, enabling
cross-referencing and propagation tracking.

### Normalization Layer

The validator bridges the two models via `normalize_to_internal_view(extraction, signals)`:

```
Contract field          →  Internal field
─────────────────────────────────────────
decisions_made[].decision_id   →  id
decisions_made[]               →  decisions[]
action_items[].action_id       →  id
action_items[].task            →  text
risks_or_open_questions (no ?) →  risks[]
risks_or_open_questions (has ?)→  questions[]
signals.questions              →  questions[] (passthrough)
signals.assumptions            →  assumptions[] (passthrough)
signals.risks                  →  risks[] (passthrough)
```

**The normalized view is used exclusively for:**
- Propagation checks (source → study_state)
- study_state validation

**The normalized view never:**
- Mutates original contract artifacts
- Replaces the external contract
- Is written back to disk

### Migration Guidance

If and when the pipeline begins emitting data in the internal normalized format
rather than the contract format, that transition must be **explicit**:

1. Update the contract in `contracts/` to reflect the new wire format.
2. Update `contracts/examples/` with a valid governed example.
3. Update `normalize_to_internal_view` to handle the new format (passthrough
   if already normalized).
4. Update the tests to validate both the old contract and the new format.

Do **not** silently change which format the pipeline emits.  Schema drift is
a governed failure mode documented in `docs/system-failure-modes.md`.

---

## Validation Report Guarantee

`validation_report.json` is **always** written to the artifact package directory
when the pipeline reaches the validation stage, regardless of outcome:

- Pass → `status: pass`
- Warnings only → `status: pass_with_warnings`
- Any error → `status: fail`

If the report file cannot be written (e.g., permission error), a
`validation_error` finding is appended to the in-memory result and the
caller's `ValidationResult` still contains all findings.

---

## Crash-Proofing Rules

The validator must never raise a runtime exception due to malformed model output.

| Scenario | Safe Handling |
|---|---|
| `classification` is a list or dict | Emit `schema_error` finding; skip set lookup |
| Item `id` is unhashable (list/dict) | Skip in ID comparison; emit propagation warning if counts differ |
| Normalization raises unexpectedly | Emit `schema_error` finding; skip propagation checks |
| JSON file cannot be parsed | Emit `validation_error` finding; continue with remaining checks |

The general rule: **any unexpected type → structured finding, validator continues**.
