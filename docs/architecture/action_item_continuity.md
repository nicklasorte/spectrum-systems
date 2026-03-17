# Action Item Continuity

**Status:** Active  
**Version:** 1.0.0  
**Date:** 2026-03-17  
**Scope:** Meeting Minutes Engine (SYS-006), Working Paper Review Engine (SYS-007), Spectrum Study Compiler (SYS-004)

---

## Purpose

Action items are the connective tissue between the coordination loop (meetings → transcripts → minutes) and the document production loop (engineering tasks → working paper → review → adjudication).  This document defines:

- How action items are classified
- How they propagate from meeting minutes into the study state and working paper
- What validation the system applies to ensure no action item is dropped

---

## Classification Types

Action items are classified by the phase of the study in which they arise and the role they play in driving work forward.

### Type A — Engineering Task

An action item that requires engineering analysis, simulation, measurement, or data collection.

**Characteristics:**
- Owner is a technical role (Ops Lead, Systems Engineer, Test Lead)
- Output is an engineering artifact (report section, dataset, simulation run)
- Maps to a work item in the document production loop

**Example:** "Run interference margin sensitivity test with updated antenna configuration by March 26."

---

### Type B — Coordination Task

An action item that requires coordination, communication, or logistics.

**Characteristics:**
- Owner is a program or administrative role (Program Manager, Contracts Lead)
- Output is a communication, confirmation, or logistics update
- May or may not produce an engineering artifact

**Example:** "Confirm alternate vendor lead time for antenna delivery by March 21."

---

### Type C — Decision-Enabling Task

An action item whose completion is required before a pending decision can be made.

**Characteristics:**
- Directly linked to an open question or risk in the study state
- Completion resolves the associated risk or answers the open question
- May be engineering or coordination in nature

**Example:** "Identify secondary vendor before confirming antenna delivery schedule."

---

### Type D — Carry-Forward Item

An action item from a prior meeting that remains open.

**Characteristics:**
- `status` is `open` at the time of the current meeting
- Re-extracted from the transcript during the action walkthrough
- May have a revised due date or owner

Carry-forward items must be re-linked to their original study_state `action_item` ID when the item has been previously tracked.

---

## Propagation Rules

### From transcript to study_state

1. The extraction engine identifies action items in the transcript (SIG-002).
2. Each action item is written to `structured_extraction.action_items` with the full contract shape.
3. `build_study_state()` maps all `structured_extraction.action_items` into `study_state.action_items`.
4. Each mapped item carries `source: "structured_extraction"` and an empty `cross_ref` list.

### From study_state into working paper

When the study state is consumed by the Working Paper Review Engine (SYS-007) or the Spectrum Study Compiler (SYS-004):

1. All `study_state.action_items` with `status: "open"` are surfaced in the working paper's open items section.
2. Engineering tasks (Type A) are linked to the relevant section of the working paper where the analysis is expected.
3. Decision-enabling tasks (Type C) are linked to the associated open question or risk.
4. Coordination tasks (Type B) are included in the action register but not linked to working paper sections.

### Status transitions

| Event | Status before | Status after |
|-------|--------------|--------------|
| Item assigned at meeting | — | `open` |
| Owner confirms work started | `open` | `in_progress` |
| Engineering output produced | `in_progress` | `done` |
| Dependency not met | any | `blocked` |
| Item re-raised at next meeting | `done` | re-extracted as new item |

---

## Validation Expectations

The validation layer in `artifact_packager.validate_package()` enforces:

1. **Count match** — the number of action items in `study_state.action_items` must equal the number in `structured_extraction.action_items`.  A mismatch is a validation error.
2. **Required fields present** — every action item in the study state must have `id`, `task`, `owner`, `due_date`, `status`, and `source`.
3. **No silent drops** — items are never silently discarded.  If an action item cannot be mapped, it must appear in the `validation_report.json` with an explanation.

The no-dropped-signal rule (see `docs/architecture/system_philosophy.md`) applies to action items in full: every action item extracted from a transcript must appear in the study state.

---

## Cross-Reference Convention

Each action item carries a `cross_ref` list that holds IDs of related objects:

- Link to a `risk` ID when the action item resolves a tracked risk
- Link to a `decision` ID when the action item is required to implement a decision
- Link to a `question` ID when the action item answers an open question

Cross-references are populated during enrichment cycles, not during initial construction.

---

## Source Module

Action item mapping is implemented in:

```
spectrum_systems/modules/study_state.py  →  _map_action_items()
```

Validation is implemented in:

```
spectrum_systems/modules/artifact_packager.py  →  validate_package()
```

---

## See Also

- `docs/architecture/study_state_model.md` — full study state schema
- `docs/architecture/signal_extraction_model.md` — how SIG-002 action items are extracted
- `docs/architecture/system_philosophy.md` — no-dropped-signal rule
- `cases/meeting_minutes/signal-extraction.yaml` — SIG-002 specification
