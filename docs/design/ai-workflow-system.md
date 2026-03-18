# AI Workflow System — Context Assembly Layer

## Purpose

This document describes the Context Assembly Layer (Prompt AL), which is the
governed, deterministic subsystem that constructs the exact inputs provided to
every AI task in the Spectrum Systems platform.

The layer enforces context structure, budget constraints, prioritisation rules,
and full traceability.  All AI calls must flow through this layer; raw inputs
must never be sent directly to a model.

---

## Module location

```
spectrum_systems/modules/ai_workflow/context_assembly.py
```

---

## Schemas

| Schema | Purpose |
|--------|---------|
| `contracts/schemas/context_bundle.schema.json` | Governed context bundle — the exact input handed to an AI task |
| `contracts/schemas/context_assembly_record.schema.json` | Traceability record produced alongside every bundle |

---

## Context Bundle

A context bundle (`context_bundle.schema.json`) contains all information the AI
task needs, divided into named sections:

| Section | Priority | Description |
|---------|----------|-------------|
| `primary_input` | 1 (highest) | Primary input payload — always included, never truncated |
| `policy_constraints` | 2 | Governing constraints and rules relevant to the task |
| `prior_artifacts` | 3 | Prior artifacts (decisions, outputs) that provide historical context |
| `retrieved_context` | 4 | Retrieved artifact fragments ordered by relevance |
| `glossary_terms` | 5 | Domain glossary entries for consistent terminology |
| `unresolved_questions` | 6 (lowest) | Open questions included as context |

Additional administrative fields: `context_id`, `task_type`, `metadata`,
`token_estimates`, `truncation_log`, `priority_order`.

### Determinism guarantee

`context_id` is derived from a SHA-256 digest of `task_type` and
`primary_input`.  Identical inputs always produce the same bundle shape.

---

## Context Assembly Record

A context assembly record (`context_assembly_record.schema.json`) is produced
alongside every bundle and captures:

- Which sections were included or excluded
- Token budget and usage
- All overflow and truncation actions taken
- Retrieval status (`available` / `unavailable`)
- Non-fatal warnings

The record is the primary instrument for traceability, debugging, and audit.

---

## Budget Enforcement

Budget enforcement is controlled by a **context budget policy** dict:

```python
{
    "total_budget_tokens": 4000,
    "input_reservation": 1000,
    "policy_constraint_reservation": 500,
    "retrieval_reservation": 1000,
    "output_reservation": 500,
    "overflow_action": "truncate_retrieval"  # or "reject_call" or "escalate"
}
```

### Rules

1. **No silent truncation** — every truncation is appended to `truncation_log`.
2. `primary_input` is never truncated regardless of budget.
3. `policy_constraints` is truncated to `policy_constraint_reservation` tokens when over budget.
4. `retrieved_context` is truncated to `retrieval_reservation` tokens when over budget.
5. If the total bundle still exceeds `total_budget_tokens` after section-level truncation,
   the `overflow_action` is enforced:
   - `truncate_retrieval` — removes `retrieved_context` entirely and logs the action.
   - `reject_call` — raises `ContextBudgetExceededError(escalation_required=False)`.
   - `escalate` — raises `ContextBudgetExceededError(escalation_required=True)`.

### Validation

The policy is validated before any budget is applied.  `ValueError` is raised
for: missing required keys, unknown `overflow_action`, negative reservations,
or a reservation sum that exceeds `total_budget_tokens`.

---

## Prioritisation Rules

Section ordering is fixed and deterministic:

1. `primary_input`
2. `policy_constraints`
3. `prior_artifacts`
4. `retrieved_context`
5. `glossary_terms`
6. `unresolved_questions`

Applied by `prioritize_context_elements(bundle)`, which returns a new bundle
with a `priority_order` key recording the final ordering.

---

## Retrieval Interface (Stub)

The retrieval interface is defined but not implemented:

```python
def retrieve_context(
    query: str,
    task_type: str,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    ...
```

Return schema per item:

| Field | Type | Description |
|-------|------|-------------|
| `artifact_id` | str | Artifact identifier |
| `content` | str | Retrieved text fragment |
| `relevance_score` | float (0–1) | Relevance score |
| `provenance` | dict | Source provenance |

When retrieval is unavailable the function returns `[]` and
`metadata.retrieval_status` is set to `"unavailable"` in the bundle.

---

## Token Estimation

Lightweight, consistent estimation (no model tokeniser required):

```python
estimate_tokens(text: str) -> int
estimate_bundle_tokens(bundle: dict) -> dict[str, int]
```

Uses a fixed characters-per-token ratio (`_CHARS_PER_TOKEN = 4.0`).  Not
exact, but consistent: calling with the same input always returns the same
value.

---

## Public API

```python
from spectrum_systems.modules.ai_workflow.context_assembly import (
    build_context_bundle,
    apply_context_budget,
    prioritize_context_elements,
    enforce_overflow_policy,
    build_assembly_record,
    estimate_tokens,
    estimate_bundle_tokens,
    retrieve_context,
    ContextBudgetExceededError,
)
```

### `build_context_bundle`

```python
bundle = build_context_bundle(
    task_type="meeting_minutes",
    input_payload={"transcript": "...", "meeting_id": "MTG-001"},
    source_artifacts=[{"artifact_id": "DEC-001", ...}],
    config={
        "budget_policy": {...},
        "policy_constraints": "...",
        "glossary_terms": [...],
        "unresolved_questions": [...],
    },
)
```

### `build_assembly_record`

```python
record = build_assembly_record(bundle, policy=policy)
```

---

## Reliability Rules

- No silent fallback behaviour.
- Deterministic outputs for identical inputs.
- Explicit errors for invalid policy configurations.
- Full traceability via `context_assembly_record`.
- No external dependencies beyond the Python standard library.
