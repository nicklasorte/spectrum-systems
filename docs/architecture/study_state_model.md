# Study State Model

**Status:** Active  
**Version:** 1.0.0  
**Date:** 2026-03-17  
**Scope:** Meeting Minutes Engine (SYS-006), Spectrum Study Compiler (SYS-004), downstream advisory systems

---

## Purpose

The study state is the central in-memory and on-disk record of everything known about an active spectrum engineering study at a given moment in time.  It is built incrementally: an initial study_state is constructed from the first meeting's extraction output and signals, then enriched as the study progresses through coordination loops, working paper reviews, and adjudication cycles.

The study state model defines:
- The schema for the study_state document
- The objects contained in each field
- The relationships between objects
- The lifecycle of the document

---

## Schema

Every study_state document produced by the system conforms to the following top-level shape:

```json
{
  "schema_version": "1.0.0",
  "generated_at": "<ISO-8601 timestamp>",
  "questions": [],
  "assumptions": [],
  "risks": [],
  "action_items": [],
  "decisions": [],
  "issues": [],
  "evidence": [],
  "data_needs": [],
  "stakeholder_positions": []
}
```

All nine domain lists are **required** and must be present even if empty.

---

## Object Definitions

### `action_items`

Discrete tasks assigned to an individual or role during the study.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique action item ID (e.g. `AI-XXXXXXXX`) |
| `task` | string | yes | Description of the task |
| `owner` | string | yes | Person or role responsible |
| `due_date` | string\|null | yes | ISO-8601 date or null if not stated |
| `status` | string | yes | `open`, `in_progress`, `done`, `blocked` |
| `dependencies` | list\|null | no | Other item IDs this depends on |
| `source` | string | yes | Origin: `structured_extraction`, `review`, etc. |
| `cross_ref` | list | yes | IDs of related decisions, risks, or issues |

### `risks`

Risks and open questions requiring tracking or follow-up.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique risk ID (e.g. `RSK-XXXXXXXX`) |
| `description` | string | yes | Description of the risk or question |
| `impact` | string\|null | yes | Assessed impact level |
| `owner` | string\|null | yes | Person or role monitoring the risk |
| `target_resolution_date` | string\|null | yes | ISO-8601 date or null |
| `confidence` | number\|null | no | Extraction confidence (0.0–1.0) |
| `source` | string | yes | Origin: `signals`, `review`, etc. |
| `cross_ref` | list | yes | IDs of related action items or decisions |

### `decisions`

Resolved commitments or conclusions reached during the study.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique decision ID (e.g. `DEC-XXXXXXXX`) |
| `decision` | string | yes | Text of the decision |
| `rationale` | string\|null | yes | Reasoning behind the decision |
| `decision_owner` | string\|null | yes | Person or role who made the decision |
| `agenda_item` | string\|null | no | Associated meeting agenda item |
| `date_made` | string\|null | yes | ISO-8601 date or null |
| `revisit_trigger` | string\|null | no | Condition that would trigger revisit |
| `confidence` | number\|null | no | Extraction confidence (0.0–1.0) |
| `source` | string | yes | Origin: `signals`, `review`, etc. |
| `cross_ref` | list | yes | IDs of related action items or risks |

### `questions`

Open questions raised during the study that have not yet been resolved.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique question ID |
| `question` | string | yes | Text of the question |
| `raised_by` | string\|null | no | Person who raised it |
| `raised_at` | string\|null | no | ISO-8601 timestamp |
| `status` | string | yes | `open`, `resolved`, `deferred` |
| `source` | string | yes | Origin |
| `cross_ref` | list | yes | Related item IDs |

### `assumptions`

Explicit or implicit assumptions recorded during the study.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique assumption ID |
| `assumption` | string | yes | Text of the assumption |
| `basis` | string\|null | no | Evidence or reasoning |
| `owner` | string\|null | no | Person or role responsible |
| `status` | string | yes | `active`, `invalidated`, `under_review` |
| `source` | string | yes | Origin |
| `cross_ref` | list | yes | Related item IDs |

### `issues`

Unresolved issues requiring escalation or human review.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique issue ID |
| `description` | string | yes | Description of the issue |
| `severity` | string | yes | `blocking`, `high`, `medium`, `low` |
| `owner` | string\|null | no | Person or role responsible |
| `status` | string | yes | `open`, `resolved`, `escalated` |
| `source` | string | yes | Origin |
| `cross_ref` | list | yes | Related item IDs |

### `evidence`

Referenced data, documents, or prior results cited during the study.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique evidence ID |
| `title` | string | yes | Human-readable title |
| `artifact_ref` | string\|null | no | Path or ID of the referenced artifact |
| `type` | string | yes | `measurement`, `simulation`, `document`, `prior_study` |
| `source` | string | yes | Origin |

### `data_needs`

Explicit requests for additional data or analysis identified during the study.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique data need ID |
| `description` | string | yes | What is needed and why |
| `owner` | string\|null | no | Person or role responsible for acquiring it |
| `priority` | string | yes | `critical`, `high`, `medium`, `low` |
| `status` | string | yes | `open`, `in_progress`, `fulfilled` |
| `source` | string | yes | Origin |

### `stakeholder_positions`

Positions, preferences, or constraints attributed to named stakeholders.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique position ID |
| `stakeholder` | string | yes | Name or role of the stakeholder |
| `position` | string | yes | Description of their position |
| `meeting_ref` | string\|null | no | Meeting where the position was stated |
| `source` | string | yes | Origin |

---

## Relationships

```
action_items ──cross_ref──▶ decisions
action_items ──cross_ref──▶ risks
decisions    ──cross_ref──▶ risks
risks        ──cross_ref──▶ action_items
questions    ──cross_ref──▶ risks
assumptions  ──cross_ref──▶ decisions
issues       ──cross_ref──▶ action_items
evidence     ──referenced_by──▶ decisions, assumptions
data_needs   ──cross_ref──▶ questions, action_items
```

Cross-references use the `cross_ref` list field, which holds IDs of related objects in any other study_state list.

---

## Lifecycle

The study_state document progresses through the following lifecycle:

1. **Initial construction** — built from the first meeting's structured extraction and signals by `build_study_state()` in `spectrum_systems/modules/study_state.py`.
2. **Enrichment** — additional meetings, working paper reviews, and adjudication cycles append to the lists.  Existing items are updated in place (matching on `id`).
3. **Review checkpoint** — the human review stage checks that all action items have been assigned, all risks have owners, and all open questions are tracked.
4. **Archival** — when the study is closed, the final study_state is snapshotted and written to the artifact package alongside the terminal structured extraction.

The study_state is never deleted; it accumulates the full history of the study.

---

## Source Module

```
spectrum_systems/modules/study_state.py
```

Key exports:
- `empty_study_state()` — returns a zeroed document
- `build_study_state(structured_extraction, signals)` — constructs the initial state
- `validate_study_state(state)` — returns a list of validation errors
- `REQUIRED_KEYS` — list of required top-level keys
- `SCHEMA_VERSION` — current schema version string

---

## See Also

- `docs/architecture/signal_extraction_model.md` — how signals are extracted and classified
- `docs/architecture/action_item_continuity.md` — how action items propagate through the study
- `docs/architecture/system_philosophy.md` — module-first and study-state-first principles
- `spectrum_systems/modules/artifact_packager.py` — how the study_state is packaged
