# Signal Extraction Model

**Status:** Active  
**Version:** 1.0.0  
**Date:** 2026-03-17  
**Scope:** Meeting Minutes Engine (SYS-006)

---

## Purpose

Signal extraction is the process of converting an unstructured meeting transcript into a structured set of typed signals that capture the decisions, action items, risks, and open questions raised in the meeting.  This document defines:

- The signal types produced by the extraction stage
- The extraction philosophy and classification rules
- How confidence is assigned and handled
- How signals flow into the study state

---

## Signal Types

The extraction engine produces the following signal types.  Each type maps to a field in the `meeting_minutes_contract.yaml`.

### SIG-001 — Decision (`decisions_made`)

A conclusion or commitment reached by the group that affects future work, direction, or scope.

**Classification rules:**
- Explicit agreement language: "we will", "we agreed", "the group decided"
- Formal motion language: "it was decided", "approved", "confirmed"
- Resolution of a previously open question with a definitive outcome

**Required fields:** `decision_id`, `decision`, `rationale`, `decision_owner`, `agenda_item`, `date_made`  
**Optional fields:** `revisit_trigger`

**Distinction from action items:** A decision is a *resolved commitment or conclusion*.  An action item is a *future task with an owner and due date*.  Do not classify tentative proposals ("we might consider") as decisions.

---

### SIG-002 — Action Item (`action_items`)

A discrete task assigned to an individual or role with a defined owner and, where stated, a due date and dependencies.

**Classification rules:**
- Ownership language: "X will", "X is responsible for", "assigned to X"
- Due-date language: "by next week", "before the next meeting", "by `<date>`"
- Carry-forward items from a prior action walkthrough that remain open

**Required fields:** `action_id`, `task`, `owner`, `due_date`, `status`  
**Optional fields:** `dependencies`

**Handling ambiguous ownership:** If ownership is ambiguous, populate `owner` with the closest identifiable party and flag `extraction_confidence` below 0.7.  Do not fabricate due dates; leave null if none is stated.

---

### SIG-003 — Risk or Open Question (`risks_or_open_questions`)

An unresolved concern, uncertainty, dependency, or open question raised during the meeting that requires monitoring or follow-up.

**Classification rules:**
- Explicit risk language: "risk", "concern", "blocker", "dependency"
- Uncertainty language: "we are not sure", "TBD", "pending confirmation"
- Open questions: "does anyone know", "we need to find out"

**Required fields:** `issue_id`, `description`, `impact`, `owner`, `target_resolution_date`

**Distinction from decisions:** A risk or open question is *not yet resolved*.  If a concern was raised and immediately resolved in the same meeting, classify it as a decision (SIG-001) rather than a risk.

---

### SIG-004 — Executive Summary Point (`executive_summary.key_points`)

A top-level synthesis point capturing the most significant outcome, direction change, or blocker from the meeting.

**Classification rules:**
- Derived from decisions (SIG-001), action items (SIG-002), and risks (SIG-003)
- Limit to 3–5 bullet points representing the highest-impact signals
- Do not introduce information not evidenced in the transcript

Executive summary points are **syntheses**, not direct quotes.

---

### SIG-005 — Next Meeting Detail (`next_meeting`)

Logistics and tentative topics for the next scheduled meeting.

**Classification rules:**
- Explicit scheduling language: "next meeting is", "we will meet on", "the next session"
- Tentative topic statements: "we will cover", "topics for next time"

If no next meeting is scheduled, leave `next_meeting` fields null.  Do not fabricate logistics.

---

## Extraction Philosophy

### Transcript-grounded extraction

All extracted signals must be grounded in the transcript.  The extraction engine must not:
- Fabricate content that is not evidenced in the transcript
- Infer ownership without textual support
- Assign due dates that are not stated

### Signal separation

Each signal type represents a distinct semantic category.  The extraction engine must apply the classification rules to separate:
- Resolved commitments (decisions) from future tasks (action items)
- Active risks from resolved concerns (reclassified as decisions)
- Factual next-meeting details from speculative agenda items

### Complete extraction

The extraction engine must attempt to extract all instances of each signal type.  Omitting a signal that is evidenced in the transcript is a blocking failure (MISSING_REQUIRED_SIGNAL).

---

## Confidence Handling

Every SIG-001, SIG-002, and SIG-003 instance carries an `extraction_confidence` value (0.0–1.0) in its traceability block when the transcript includes timestamps and speaker labels.

| Threshold | Meaning |
|-----------|---------|
| ≥ 0.85 | High confidence — no review flag required |
| 0.70–0.84 | Acceptable confidence — proceed without flag |
| < 0.70 | Low confidence — flag for human review |
| < 0.50 | Blocking — item blocks publication until reviewed |

Items with `extraction_confidence < 0.70` must appear in the `validation_report.json` human review queue.  Items with `extraction_confidence < 0.50` block publication.

---

## Signal Flow into Study State

After the extraction stage, signals flow into the study state as follows:

| Signal | Study State Field |
|--------|-----------------|
| `decisions_made` (SIG-001) | `decisions` |
| `action_items` (SIG-002) | `action_items` (from structured_extraction) |
| `risks_or_open_questions` (SIG-003) | `risks` |

The `build_study_state()` function in `spectrum_systems/modules/study_state.py` performs this mapping.

`action_items` are sourced from `structured_extraction` (not `signals`) to preserve the full contract-shaped record including `action_id`, `status`, and `dependencies`.  Risks and decisions are sourced from `signals` to capture `extraction_confidence` and traceability metadata.

---

## Contract Anchor

Signal extraction conforms to:
- `contracts/meeting_minutes_contract.yaml` — canonical output shape
- `cases/meeting_minutes/signal-extraction.yaml` — signal type specification (v1.0.0)
- `contracts/schemas/meeting_minutes_record.schema.json` — JSON Schema for validation

---

## See Also

- `docs/architecture/study_state_model.md` — how signals populate the study state
- `docs/architecture/action_item_continuity.md` — how action items are tracked through the study
- `cases/meeting_minutes/signal-extraction.yaml` — canonical signal type spec
