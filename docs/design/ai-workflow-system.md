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

`context_id` is derived from a SHA-256 digest of **all bundle-contributing
inputs**: `task_type`, `primary_input`, sorted source artifact IDs,
`policy_constraints`, `glossary_terms`, and `unresolved_questions`.  Two
bundles that differ in any of these fields will always receive different
`context_id` values.

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
    "input_reservation": 1000,        # floor reserved for primary_input (not truncated)
    "policy_constraint_reservation": 500,
    "retrieval_reservation": 1000,
    "output_reservation": 500,        # reserved for model output (not part of the bundle)
    "overflow_action": "truncate_retrieval"  # or "reject_call" or "escalate"
}
```

`input_reservation` and `output_reservation` are counted against
`total_budget_tokens` to ensure the budget is not over-committed, but neither
section is truncated by the assembly layer — `primary_input` is always included
intact and `output_reservation` reserves headroom for the model's response,
which is outside the bundle.

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

The retrieval query is taken from `config["retrieval_query"]` when supplied.
When absent, `task_type` is used as a placeholder query.  Callers should
supply an explicit query via `config["retrieval_query"]` once real retrieval
is implemented, so the query reflects the actual content of the task.

When retrieval is unavailable the function returns `[]` and
`metadata.retrieval_status` is set to `"unavailable"` in the bundle.
When a real retrieval implementation returns an empty result set,
`retrieval_status` should be set to `"empty"` (not `"unavailable"`) to
distinguish "system ran but found nothing" from "system was not called".
The three valid values are `"available"`, `"empty"`, and `"unavailable"`.

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

---

## Multi-Pass Reasoning Layer (Prompt AM)

### Purpose

The Multi-Pass Reasoning Layer runs explicit, typed reasoning passes over a
context bundle, validates intermediate outputs, enforces pass budgets and
circuit breakers, and emits traceable pass-chain artifacts.  A single AI pass
is too weak and brittle for regulated, technical workflows; this layer provides
deterministic orchestration of multiple narrow passes.

### Module location

```
spectrum_systems/modules/ai_workflow/multi_pass_reasoning.py
```

### Schemas

| Schema | Purpose |
|--------|---------|
| `contracts/schemas/pass_chain_record.schema.json` | Governed traceability record for a complete chain execution |
| `contracts/schemas/pass_result.schema.json` | Per-pass execution record |
| `contracts/schemas/meeting_minutes/transcript_facts_output.schema.json` | Extraction pass output |
| `contracts/schemas/meeting_minutes/decisions_output.schema.json` | Decision extraction output |
| `contracts/schemas/meeting_minutes/action_items_output.schema.json` | Action item extraction output |
| `contracts/schemas/meeting_minutes/contradictions_output.schema.json` | Contradiction detection output |
| `contracts/schemas/meeting_minutes/gaps_output.schema.json` | Gap detection output |
| `contracts/schemas/meeting_minutes/adversarial_review_output.schema.json` | Adversarial review output |
| `contracts/schemas/meeting_minutes/synthesis_output.schema.json` | Synthesis pass output |

### Pass chain execution model

A pass chain is built by `build_pass_chain(task_type, context_bundle, config)`.
It resolves the canonical pass sequence for the task type, applies any per-pass
overrides, enforces confidence-method defaults, and returns a `PassChain` dict.

`execute_pass_chain(pass_chain, model_adapter, prompt_registry, task_router)`
iterates the sequence, calling the model adapter for each pass, validating
outputs, and checking the circuit breaker after every pass.  All intermediate
outputs are stored in state throughout execution so that failed chains preserve
them for debugging.

`finalize_pass_chain(state)` produces the `PassChainRecord` dict that conforms
to `pass_chain_record.schema.json`.

### Meeting-minutes canonical pass sequence

1. `transcript_extraction` — extract objective facts from transcript
2. `decision_extraction` — extract formal decisions (reasoning-class; scoring_pass)
3. `action_item_extraction` — extract action items
4. `contradiction_detection` — detect contradictions (reasoning-class; scoring_pass)
5. `gap_detection` — detect missing information (reasoning-class; scoring_pass)
6. `adversarial_review` — challenge upstream outputs (reasoning-class; scoring_pass)
7. `synthesis` — produce governed summary grounded in upstream structured artifacts

Each pass receives the context bundle plus the structured outputs of every
upstream pass in its `input_refs`.  The synthesis pass must not invent facts
not supported by upstream structured artifacts.

### Circuit breaker rules

The circuit breaker is evaluated before and after every pass.  It terminates
the chain when any of the following conditions is met:

| Condition | Effect |
|-----------|--------|
| `max_passes` total passes executed | `terminated` |
| `max_failed_passes` total failures | `terminated` or `escalated` |
| `consecutive_failure_limit` failures in a row | `terminated` or `escalated` |
| `persistent_validation_failure_limit` validation failures | `escalated` (always) |

When the `escalation_policy` is `"escalate_after_persistent_failure"`, any
termination caused by failure counts sets `escalation_required=True`.  With
`"terminate_only"`, only persistent validation failures trigger escalation.

Terminated chains write `termination_reason` and preserve all intermediate
outputs collected up to the point of termination.

### Confidence method enforcement

| Method | When to use |
|--------|-------------|
| `self_reported` | Low-risk passes (extraction, synthesis) |
| `scoring_pass` | Reasoning-class passes (decision, contradiction, gap, adversarial) |
| `heuristic` | Lightweight structural estimate |

Reasoning-class passes (`decision_extraction`, `contradiction_detection`,
`gap_detection`, `adversarial_review`) default to `scoring_pass`.  Overriding
to `self_reported` is permitted but produces a warning in the chain record.

When `scoring_pass` is used, the model adapter must implement
`invoke_scoring_pass(...)`, which is called after the main pass to produce a
traceable confidence score linked to the pass result via `scoring_pass_ref`.

### Intermediate artifact retention policy

Every pass output that completes successfully receives a deterministic
`output_ref` (`artifact:{pass_id}:{pass_type}`).  The raw output is held in
`intermediate_artifacts` in the chain state throughout execution.

For successfully completed chains, intermediates are accessible via
`intermediate_artifact_refs` in the `PassChainRecord`.  For failed or
terminated chains, all intermediates collected up to the point of failure are
preserved to support debugging and audit.

The `_raw_output` private key is stripped from pass results in the final record.

### Governance boundary

The Multi-Pass Reasoning Layer owns reasoning orchestration: pass sequencing,
output validation, circuit breaking, and confidence method enforcement.

It does **not** own:
- Context assembly (see `context_assembly.py`)
- Model invocation implementation (injected via `model_adapter`)
- Prompt storage (injected via `prompt_registry`)
- Pipeline scheduling or trigger sequencing (belongs to the pipeline engine)

### Public API

```python
from spectrum_systems.modules.ai_workflow.multi_pass_reasoning import (
    build_pass_chain,
    execute_pass_chain,
    execute_single_pass,
    validate_pass_output,
    apply_circuit_breaker,
    finalize_pass_chain,
    PassChainError,
    UnsupportedTaskTypeError,
    InvalidCircuitBreakerPolicyError,
    REASONING_CLASS_PASSES,
    MEETING_MINUTES_PASS_SEQUENCE,
)
```

### Reliability rules

- Explicit code paths only: no inferred pass sequences.
- Deterministic pass ordering: sequence is declared per task type.
- No hidden heuristics: every confidence score method is recorded.
- No silent schema downgrade: missing schema → `skipped` status, not silent pass.
- No silent prompt substitution: missing prompt → hard failure, chain terminates.
- No silent fallback on routing: version is pinned across all passes.
- No external dependencies beyond the Python standard library.
