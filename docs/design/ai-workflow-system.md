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

---

## Evaluation + Grounding Framework (Prompt AN)

### Purpose

The Evaluation + Grounding Framework provides governed, reproducible evaluation
infrastructure for the full meeting-minutes → working-paper pipeline.  It
enforces claim-level traceability, detects regressions against stored baselines,
and produces structured evidence bundles that can be used for audit and CI.

The golden path for this framework is: **Observe → Interpret → Validate**.

### Module location

```
spectrum_systems/modules/evaluation/
├── __init__.py
├── golden_dataset.py     # GoldenCase, GoldenDataset, load_all_cases, load_case
├── grounding.py          # GroundingVerifier, claim-level traceability enforcement
├── comparison.py         # compare_structural, compare_semantic
├── error_taxonomy.py     # ErrorType, EvalError, classify_error
├── regression.py         # RegressionHarness, BaselineRecord
└── eval_runner.py        # EvalResult, EvalRunner
```

### Architecture diagram

```
  ┌─────────────────────────────────────────────────────────────┐
  │                      EvalRunner                             │
  │                                                             │
  │  GoldenDataset ──► run_case() ──► ReasoningEngine.run()     │
  │       │                │                  │                 │
  │       │          PassChainRecord     PassResults            │
  │       │                │                  │                 │
  │       ▼                ▼                  ▼                 │
  │  expected_outputs  actual_outputs    latency_ms             │
  │       │                │                                    │
  │       └──► compare_structural() ──► structural_score        │
  │       └──► compare_semantic()   ──► semantic_score          │
  │                                                             │
  │  synthesized_doc ──► GroundingVerifier ──► grounding_score  │
  │                                                             │
  │  RegressionHarness ──► compare() ──► regression_detected    │
  │                                                             │
  │  ErrorTaxonomy ──► classify_error() ──► EvalError list      │
  │                                                             │
  │  ─────────────────────────────────────────────             │
  │  EvalResult { pass_fail, structural_score, semantic_score,  │
  │               grounding_score, latency_summary, error_types}│
  └─────────────────────────────────────────────────────────────┘
```

### How grounding works

Every claim in a synthesized document (e.g., a working-paper section) must
declare ``upstream_pass_refs`` — a list of pass IDs from the reasoning chain
that the claim is derived from.

The ``GroundingVerifier`` enforces three rules:

1. **Missing refs** — a claim with no ``upstream_pass_refs`` → FAIL
2. **Reference does not exist** — a declared pass ID is absent from
   ``intermediate_artifacts`` → FAIL
3. **Semantic mismatch** — the referenced artifact shares no meaningful token
   overlap with the claim text → FAIL

All grounding failures are classified by `error_taxonomy.classify_error`:

- `grounding_failure` — at least one ref exists but is invalid or mismatched
- `hallucination` — all declared refs are absent (no upstream evidence at all)

There is no silent fallback.  A claim that cannot be grounded causes
`pass_fail=False` in `EvalResult`.

### How regression works

Baselines are stored as JSON files in `data/eval_baselines/{case_id}.json`.

Each baseline record contains:
- `structural_score` — F1 from structural comparison
- `semantic_score` — F1 from semantic comparison
- `grounding_score` — fraction of grounded claims

Thresholds are configurable in `config/eval_config.yaml`
(`regression_thresholds`).  Default: **0.05** drop allowed per dimension.

When a current run's score drops below `baseline - threshold`, a
`regression_failure` error is recorded and `regression_detected=True` is set in
`EvalResult`.

To update baselines after a deliberate improvement:

```bash
python scripts/run_eval.py --all --update-baseline
```

### How to add new golden cases

1. Create a new directory under `data/golden_cases/<case_id>/`.

2. Add the required files:

```
data/golden_cases/<case_id>/
  metadata.json                  # case_id, domain, difficulty, notes
  input/
      transcript.txt             # required
      slides.pdf                 # optional
  expected_outputs/
      decisions.json             # required — list of decision objects
      action_items.json          # required — list of action item objects
      gaps.json                  # required — list of gap objects
      contradictions.json        # required — list of contradiction objects
      working_paper_sections.json  # optional
```

3. Verify structure:

```python
from pathlib import Path
from spectrum_systems.modules.evaluation.golden_dataset import validate_case_structure
errors = validate_case_structure(Path("data/golden_cases/<case_id>"))
assert errors == [], errors
```

4. Run evaluation:

```bash
python scripts/run_eval.py --case <case_id>
```

5. If the new case represents the correct expected output, record the baseline:

```bash
python scripts/run_eval.py --case <case_id> --update-baseline
```

### CLI

```bash
# Run all cases
python scripts/run_eval.py --all

# Run a single case
python scripts/run_eval.py --case case_001

# Run all and update baselines
python scripts/run_eval.py --all --update-baseline

# Run without deterministic mode
python scripts/run_eval.py --all --no-deterministic

# Custom config and output path
python scripts/run_eval.py --all --config config/eval_config.yaml --output outputs/eval_results.json
```

### Error taxonomy

| Error type | Meaning |
|---|---|
| `extraction_error` | Structured data not extracted from input |
| `reasoning_error` | Reasoning-class pass produced incorrect output |
| `grounding_failure` | Claim has invalid or mismatched upstream reference |
| `schema_violation` | Pass output failed JSON schema validation |
| `hallucination` | Claim has zero upstream evidence (all refs absent) |
| `regression_failure` | Score dropped below baseline beyond threshold |

### Reliability rules

- No ungrounded claim passes evaluation.
- No silent fallback on failures; all failures are classified.
- Evaluation must be reproducible: use `deterministic=true` for CI runs.
- System must fail loudly, not degrade quietly.
- No external dependencies beyond the Python standard library.

---

## Human Feedback Capture Layer (Prompt AO)

### Overview

The Human Feedback Capture Layer provides a governed, structured mechanism for expert reviewers to evaluate AI-generated outputs at the claim, section, or artifact level.  Feedback is a **first-class artifact** — schema-validated, uniquely identified, and stored alongside the outputs it references.

### Feedback lifecycle

```
AI Output (pass_chain_record / working_paper / slide_intelligence)
    │
    ▼
extract_claims()          — segment into reviewable claim units
    │
    ▼
ReviewSession             — iterate claims, collect structured feedback
    │
    ▼
HumanFeedbackRecord       — schema-validated, persisted to data/human_feedback/
    │
    ├──▶ FeedbackStore     — JSON storage + artifact index
    │
    ├──▶ feedback_mapping  — maps failure_type → ErrorType (AU bridge)
    │
    └──▶ EvalRunner.apply_feedback_overrides() — injects overrides into EvalResult
```

### Schema: human_feedback_record

Contract: `contracts/schemas/human_feedback_record.schema.json`

| Field | Type | Description |
|---|---|---|
| `feedback_id` | string | Unique UUID |
| `artifact_id` | string | Reviewed artifact ID |
| `artifact_type` | enum | `meeting_minutes`, `working_paper`, `slide_intelligence`, etc. |
| `target_level` | enum | `artifact` \| `section` \| `claim` |
| `target_id` | string | ID of reviewed section or claim |
| `reviewer.reviewer_id` | string | Reviewer identifier |
| `reviewer.reviewer_role` | enum | `engineer` \| `policy` \| `legal` \| `leadership` |
| `action` | enum | `accept` \| `minor_edit` \| `major_edit` \| `reject` \| `rewrite` \| `needs_support` |
| `original_text` | string | Always preserved — never overwritten |
| `edited_text` | string\|null | Required for edit/rewrite actions |
| `rationale` | string | Reviewer explanation |
| `source_of_truth` | enum | `transcript` \| `slides` \| `statute` \| `policy` \| `engineering_analysis` \| `external_reference` |
| `failure_type` | enum | AU-aligned: `extraction_error` \| `reasoning_error` \| `grounding_failure` \| `hallucination` \| `schema_violation` \| `unclear` |
| `severity` | enum | `low` \| `medium` \| `high` \| `critical` |
| `should_update.golden_dataset` | bool | Trigger golden dataset update |
| `should_update.prompts` | bool | Trigger prompt update |
| `should_update.retrieval_memory` | bool | Trigger retrieval memory update |
| `timestamp` | ISO-8601 datetime | Record creation time |

### Module structure

| Module | Path | Purpose |
|---|---|---|
| `HumanFeedbackRecord` | `spectrum_systems/modules/feedback/human_feedback.py` | Data model + schema validation |
| `FeedbackStore` | `spectrum_systems/modules/feedback/human_feedback.py` | Persist, load, list, index |
| `create_feedback_from_review` | `spectrum_systems/modules/feedback/feedback_ingest.py` | Build + validate + persist from raw reviewer input |
| `extract_claims` | `spectrum_systems/modules/feedback/claim_extraction.py` | Segment documents into reviewable units |
| `ReviewSession` | `spectrum_systems/modules/feedback/review_session.py` | Multi-claim iterative review session |
| `map_feedback_to_error_type` | `spectrum_systems/modules/feedback/feedback_mapping.py` | Bridge to AU error taxonomy |

### Integration with EvalRunner (AN)

After a `run_case()` call, human feedback can be injected via:

```python
updated_result = runner.apply_feedback_overrides(eval_result, feedback_records)
```

- Original `EvalResult` is **never mutated** (returns a new dataclass copy).
- Overrides are stored in `EvalResult.human_feedback_overrides`.
- Each override includes a `human_disagrees_with_system` flag.
- `to_dict()` includes the overrides for serialization into eval reports.

### CLI usage

```bash
python scripts/run_feedback_session.py --artifact ARTIFACT_ID --reviewer USER_ID

# With all options
python scripts/run_feedback_session.py \
  --artifact wp-section-001 \
  --reviewer eng-alice \
  --role engineer \
  --artifact-type working_paper \
  --artifact-file path/to/artifact.json \
  --output outputs/session_summary.json
```

### How feedback feeds downstream systems

| Downstream system | How it uses feedback |
|---|---|
| **AU — Error taxonomy** | `map_feedback_to_error_type()` maps every feedback record to a typed `ErrorType`, enabling failure pattern analysis |
| **AV — Clustering** | `failure_type` + `severity` fields enable clustering of feedback by failure mode |
| **AW — Prompt improvement** | `should_update.prompts` flag + `original_text` / `edited_text` pairs provide training signal |
| **AZ — Data flywheel** | `should_update.golden_dataset` flag identifies cases for golden dataset expansion |

### Strict rules

- No unstructured-only feedback: all feedback must pass schema validation before persistence.
- Feedback must map to a specific `artifact_id` + `target_id`.
- No silent overwriting: `original_text` is always preserved alongside `edited_text`.
- Feedback is additive: artifacts are never mutated by the feedback system.

---

## Observability + Metrics Layer (Prompt AP)

### Purpose

The Observability + Metrics Layer is the system's nervous system.  It captures
structured, queryable metrics for every AI workflow event — pass executions,
evaluation runs, and human feedback events — and surfaces actionable insight
into where the system is failing, what error types dominate, which passes are
weakest, and where humans disagree with the system.

### Module location

```
spectrum_systems/modules/observability/
  __init__.py
  metrics.py      # ObservabilityRecord, MetricsStore
  aggregation.py  # Aggregation functions
  trends.py       # Run-over-run trend tracking
```

### Schema

| Schema | Purpose |
|--------|---------|
| `contracts/schemas/observability_record.schema.json` | Governed observability record — every metric event |

### Metric definitions

Every observability record captures:

| Field | Type | Description |
|-------|------|-------------|
| `record_id` | string | Unique identifier |
| `timestamp` | string (ISO-8601) | Time of emission |
| `context.artifact_id` | string | Artifact being measured |
| `context.artifact_type` | string | Type of artifact |
| `context.case_id` | string (optional) | Golden case ID (for eval records) |
| `context.pipeline_stage` | enum | `observe` \| `interpret` \| `validate` \| `learn` |
| `pass_info.pass_id` | string | Unique pass identifier |
| `pass_info.pass_type` | string | Pass type (e.g. `extraction`, `reasoning`) |
| `metrics.structural_score` | float (0–1) | Structural F1 score |
| `metrics.semantic_score` | float (0–1) | Semantic F1 score |
| `metrics.grounding_score` | float (0–1) | Fraction of claims grounded |
| `metrics.latency_ms` | int | Latency in milliseconds |
| `metrics.tokens_used` | int (optional) | Tokens consumed |
| `flags.schema_valid` | bool | Schema validation passed |
| `flags.grounding_passed` | bool | All claims grounded |
| `flags.regression_passed` | bool | No regression detected |
| `flags.human_disagrees` | bool | Human reviewer disagreed |
| `error_summary.error_types` | array | AU-aligned error types |
| `error_summary.failure_count` | int | Total failures |

### Aggregation logic

`spectrum_systems/modules/observability/aggregation.py` provides:

| Function | Returns |
|----------|---------|
| `compute_pass_metrics(records)` | Avg scores and failure rates per pass type |
| `compute_error_distribution(records)` | Count per error type, top error type |
| `compute_human_disagreement(records)` | Disagreement rate per pass and per artifact |
| `compute_grounding_failure_rate(records)` | Grounding failure rate per pass type |
| `compute_latency_stats(records)` | Mean, p95, max latency |
| `compute_weakest_passes(records)` | Passes ordered by failure rate |

### Integration with evaluation (AN)

`EvalRunner` accepts an optional `metrics_store` parameter.  When configured,
an `ObservabilityRecord` is emitted automatically after every `run_case` call:

```python
from spectrum_systems.modules.observability.metrics import MetricsStore
from spectrum_systems.modules.evaluation.eval_runner import EvalRunner

store = MetricsStore()
runner = EvalRunner(reasoning_engine=engine, metrics_store=store)
runner.run_case(case)  # → emits ObservabilityRecord automatically
```

### Integration with feedback (AO)

`create_feedback_from_review` accepts an optional `metrics_store` parameter.
When provided, an `ObservabilityRecord` with `human_disagrees=True` is emitted
for every recorded feedback event:

```python
from spectrum_systems.modules.observability.metrics import MetricsStore
from spectrum_systems.modules.feedback.feedback_ingest import create_feedback_from_review

store = MetricsStore()
create_feedback_from_review(artifact, reviewer_input, metrics_store=store)
# → emits ObservabilityRecord with human_disagrees=True
```

### CLI report generation

```bash
# Report across all stored records
python scripts/run_metrics_report.py --all

# Report filtered to a specific golden case
python scripts/run_metrics_report.py --case CASE_ID

# Custom store and output paths
python scripts/run_metrics_report.py --all \
  --store data/observability/ \
  --output outputs/metrics_report.json
```

Output includes:

- Console summary: weakest passes, top error types, grounding failure rate,
  human disagreement rate, latency statistics
- JSON report at `outputs/metrics_report.json`

### Trend tracking

`spectrum_systems/modules/observability/trends.py` enables run-over-run comparison:

```python
from spectrum_systems.modules.observability.trends import compare_runs, save_snapshot

# Save a snapshot after each eval run
save_snapshot(records, label="run_2026_03_18")

# Compare current run to a previous one
trend = compare_runs(current_records, previous_records)
# → returns deltas in scores, error rates, latency
```

Snapshots are stored under `data/observability_history/`.

### How observability feeds downstream systems

| Downstream system | How observability feeds it |
|---|---|
| **AU — Error taxonomy** | `error_types` field in every record uses AU-aligned `ErrorType` values |
| **AV — Failure clustering** | `error_types` + `flags` fields enable clustering of failure modes across runs |
| **AR — Regression** | `flags.regression_passed` + trend deltas surface score regressions |
| **AW — Prompt improvement** | Aggregated grounding scores and human disagreement rates identify prompts to improve |

### Strict rules

- No unstructured logs: every metric must be an `ObservabilityRecord`.
- Every record must map to a `pass_id` and `artifact_id`.
- Observability must never mutate system outputs.
- Missing metrics are failures: do not silently skip emission.
- Human disagreement must always be captured when present (`human_disagrees=True`).
- All `error_types` must align with `ErrorType` from AU error taxonomy.

---

## Prompt Regression Harness + Hard Enforcement (Prompt AR)

### Role of AR in the control loop

The Regression Harness (AR) converts evaluation and observability outputs into
hard gates.  It prevents silent degradation when prompts, model adapters,
scoring logic, or pass-chain behaviour change.  AR sits between the evaluation
layer (AN) and the observability/trend layer (AP), consuming their outputs and
producing governed regression reports that can block releases.

### Text architecture diagram

```
golden cases
    |
    v
eval (AN)  ─────────────────────────────►  eval_results.json
    |                                             |
    v                                             |
observability (AP)  ─────────────────────►  metrics_report.json
                                                  |
                          ┌───────────────────────┘
                          v
              regression baseline (named)
                          |
                          v
              candidate comparison
                          |
                          v
               gate evaluation (policy)
                          |
                 ┌────────┴────────┐
                 v                 v
             PASS (0)           FAIL (2)
                          |
                          v
                  regression_report.json
```

### Module location

```
spectrum_systems/modules/regression/
    __init__.py        — public exports
    harness.py         — RegressionHarness, RegressionPolicy, RegressionReport
    baselines.py       — BaselineManager (save/load/list/describe)
    gates.py           — evaluate_dimension_gate, evaluate_policy_gates
    attribution.py     — pass-level regression attribution
    recommendations.py — rule-based recommendation engine
```

### Schemas

| Schema | Purpose |
|--------|---------|
| `contracts/schemas/regression_policy.schema.json` | Governed policy defining thresholds and hard-fail dimensions |
| `contracts/schemas/regression_report.schema.json` | Governed report produced by every regression check |

### Default policy

`config/regression_policy.json` ships with the following defaults:

| Dimension | Threshold | Hard fail |
|-----------|-----------|-----------|
| `grounding_score` | drop > 0.03 | yes |
| `structural_score` | drop > 0.05 | yes |
| `semantic_score` | drop > 0.08 | yes |
| `latency` | increase > 25% | no (warning) |
| `human_disagreement` | increase > 20% | no (warning) |

Grounding is stricter than semantic; structural is stricter than latency.
Latency and human disagreement default to warnings, not hard failures, unless
the policy is overridden.

### Baseline lifecycle

1. **Create** — Run `scripts/run_regression_check.py --create-baseline NAME`
   after a known-good eval + observability run.  The baseline is stored under
   `data/regression_baselines/{NAME}/` with eval_results, observability_records,
   and metadata.
2. **Compare** — Run `scripts/run_regression_check.py --baseline NAME` to
   compare the current run against the stored baseline.
3. **Update** — Pass `--update-baseline` to explicitly replace a baseline.
   Silent overwrites are forbidden.
4. **Describe** — `BaselineManager.describe_baseline(name)` returns the
   baseline metadata without loading scores.

### Hard fail vs warning behaviour

| Severity | Condition | Exit code |
|----------|-----------|-----------|
| `hard_fail` | Dimension threshold exceeded AND `hard_fail_dimensions[dim]=true` | 2 |
| `warning` | Threshold exceeded AND `hard_fail_dimensions[dim]=false` | 1 |
| `info` | Within threshold | 0 |

Hard failures block the pipeline.  Warnings are surfaced but do not block
unless `--strict-warnings` is passed to the CLI.

### Deterministic mode requirements

When `deterministic_required: true` in the policy, a candidate run that did
not use deterministic mode (`temperature=0`, fixed seed) is a hard failure.

The baseline metadata records `deterministic_mode`.  If the candidate's
determinism mode differs from the baseline's, a warning is emitted.

### How AR consumes AN + AP outputs

- **AN (eval)** — `EvalRunner.write_report()` produces `eval_results.json`
  (a list of `EvalResult.to_dict()` dicts).  `RegressionHarness` loads this
  via `eval_result_to_dict()`.
- **AP (observability)** — `MetricsStore` emits `ObservabilityRecord` dicts.
  `RegressionHarness` normalises nested schema dicts to a flat format via
  `observability_record_to_dict()` / `_flatten_obs_record_dict()`.

If pass-level observability is not available for some records, AR explicitly
reports partial attribution rather than fabricating precision.

### How AR prepares the system for AU / AV / AW

- **AU (error taxonomy)** — Worst regression entries carry `severity`,
  `dimension`, and `explanation` fields aligned with AU taxonomy.
- **AV (failure clustering)** — `worst_regressions` array enables downstream
  clustering of regression signals by case, pass, and dimension.
- **AW (prompt improvement)** — Grounding and semantic regression signals
  identify which prompts to target for improvement in the AW layer.


---

## Error Taxonomy System (Prompt AU)

The Error Taxonomy System (AU) is the canonical governed classification layer
for failures produced by the evaluation (AN), feedback (AO), observability
(AP), and regression (AR) systems.

### Why canonical codes matter

Before AU, each subsystem used ad hoc error labels:

- AN used the `ErrorType` enum (`extraction_error`, `grounding_failure`, …)
- AO used `failure_type` strings from human feedback records
- AP captured `error_types` as lists of ErrorType values
- AR described regressions by dimension name and delta

These coarse signals could not be compared across sources, clustered for
trend analysis, or routed to specific remediation targets without
re-interpretation at every consumer.

AU replaces scattered ad hoc labels with a single governed catalog of
stable dot-notation codes (e.g. `GROUND.MISSING_REF`, `REGRESS.GROUNDING_DROP`)
that are the same regardless of which system detected the failure.

### Taxonomy structure

The catalog is stored at `config/error_taxonomy_catalog.json` and validated
against `contracts/schemas/error_taxonomy_catalog.schema.json`.

**Families and subtypes:**

| Family | Example codes |
|--------|--------------|
| `INPUT` | `INPUT.BAD_TRANSCRIPT_QUALITY`, `INPUT.MISSING_CONTEXT` |
| `EXTRACT` | `EXTRACT.MISSED_DECISION`, `EXTRACT.MISSED_ACTION_ITEM`, `EXTRACT.FALSE_EXTRACTION` |
| `REASON` | `REASON.BAD_INFERENCE`, `REASON.CONTRADICTION_MISSED`, `REASON.GAP_MISSED` |
| `GROUND` | `GROUND.MISSING_REF`, `GROUND.INVALID_REF`, `GROUND.WEAK_SUPPORT`, `GROUND.UNTRACEABLE_CLAIM` |
| `SCHEMA` | `SCHEMA.INVALID_OUTPUT`, `SCHEMA.MISSING_REQUIRED_FIELD`, `SCHEMA.TYPE_MISMATCH` |
| `HALLUC` | `HALLUC.UNSUPPORTED_ASSERTION`, `HALLUC.INVENTED_DETAIL` |
| `REGRESS` | `REGRESS.STRUCTURAL_DROP`, `REGRESS.SEMANTIC_DROP`, `REGRESS.GROUNDING_DROP`, `REGRESS.LATENCY_SPIKE` |
| `RETRIEVE` | `RETRIEVE.IRRELEVANT_MEMORY`, `RETRIEVE.MISSED_RELEVANT_MEMORY` |
| `HUMAN` | `HUMAN.REVIEWER_DISAGREEMENT`, `HUMAN.NEEDS_SUPPORT`, `HUMAN.REWRITE_REQUIRED` |

Each subtype carries:
- `default_severity` (low / medium / high / critical)
- `detection_sources` (which systems can detect it)
- `remediation_target` (prompt / schema / grounding / model / input_quality / retrieval / pipeline_control / human_process)
- `examples` (illustrative cases)

### Module location

```
spectrum_systems/modules/error_taxonomy/
    __init__.py     — public exports
    catalog.py      — ErrorSubtype, ErrorFamily, ErrorTaxonomyCatalog
    normalize.py    — normalization functions (source signal → classification)
    classify.py     — ErrorClassificationRecord, ErrorClassifier
    bridge.py       — backward compatibility bridge (legacy ErrorType → AU codes)
    aggregation.py  — count_by_family, count_by_subtype, identify_highest_impact_subtypes
```

### Schemas

| Schema | Purpose |
|--------|---------|
| `contracts/schemas/error_taxonomy_catalog.schema.json` | Governed catalog structure |
| `contracts/schemas/error_classification_record.schema.json` | Governed classification record |

### How AU consumes AN / AO / AP / AR

**AN (evaluation)** — After `EvalRunner` produces failures, `ErrorClassifier.classify_eval_result()` maps each failure into one or more `ClassificationResult` entries and wraps them in an `ErrorClassificationRecord`. Schema errors → `SCHEMA.*`, grounding failures → `GROUND.*` or `HALLUC.*`, reasoning passes → `REASON.*`, extraction passes → `EXTRACT.*`.

**AO (feedback)** — When a `HumanFeedbackRecord` is saved, `ErrorClassifier.classify_feedback_record()` maps `failure_type` and `action` into canonical codes. `needs_support` → `HUMAN.NEEDS_SUPPORT` + `GROUND.WEAK_SUPPORT`. `rewrite` → `HUMAN.REWRITE_REQUIRED`. The raw record is preserved in `raw_inputs`.

**AP (observability)** — AU does **not** mutate observability records. Instead, `ErrorClassifier.classify_observability_record()` reads the flag and score fields from an `ObservabilityRecord` dict and derives taxonomy-coded classifications. `grounding_passed=false` → `GROUND.MISSING_REF` or `HALLUC.UNSUPPORTED_ASSERTION`. `human_disagrees=true` → `HUMAN.REVIEWER_DISAGREEMENT`.

**AR (regression)** — `ErrorClassifier.classify_regression_report()` iterates `worst_regressions` entries and maps each `dimension` to a `REGRESS.*` code: `grounding_score` → `REGRESS.GROUNDING_DROP`, `structural_score` → `REGRESS.STRUCTURAL_DROP`, `latency` → `REGRESS.LATENCY_SPIKE`.

### Backward compatibility bridge

`bridge.py` maps the legacy `ErrorType` enum values from AN/AP/AO into AU codes without breaking existing callers:

```python
from spectrum_systems.modules.error_taxonomy.bridge import map_legacy_error_type
from spectrum_systems.modules.evaluation.error_taxonomy import ErrorType

codes = map_legacy_error_type(ErrorType.grounding_failure)
# → ["GROUND.MISSING_REF"]
```

### How AU prepares AV and AW

**AV (failure clustering)** — `ErrorClassificationRecord` objects are stored under `data/error_classifications/` as flat JSON files. Each record carries stable `error_code` values, `confidence`, `taxonomy_version`, and context (case_id, pass_id, source_system). AV can load all records via `ErrorClassificationRecord.list_all()` and cluster by family, subtype, or remediation_target using the `aggregation` module.

**AW (prompt improvement)** — `identify_highest_impact_subtypes()` ranks subtypes by count × severity_weight, surfacing which prompts to target first. `count_by_remediation_target()` directs prompt engineers to the right layer (`prompt`, `grounding`, `retrieval`, etc.).

### Raw signal → canonical code examples

| Source | Raw signal | Canonical code(s) |
|--------|-----------|-------------------|
| AN eval | `schema_errors: ["'decisions' is required"]` | `SCHEMA.MISSING_REQUIRED_FIELD` |
| AN eval | `missing_refs: ["ref-1"], upstream_pass_refs: ["ref-1"]` (all missing) | `HALLUC.UNSUPPORTED_ASSERTION` |
| AN eval | `mismatched_refs: ["ref-2"]` | `GROUND.WEAK_SUPPORT` |
| AN eval | `pass_type: "contradiction_detection"` | `REASON.CONTRADICTION_MISSED` |
| AO feedback | `action: "needs_support"` | `HUMAN.NEEDS_SUPPORT`, `GROUND.WEAK_SUPPORT` |
| AO feedback | `failure_type: "hallucination"` | `HALLUC.UNSUPPORTED_ASSERTION` |
| AP observability | `grounding_passed: false, grounding_score: 0.0` | `HALLUC.UNSUPPORTED_ASSERTION` |
| AP observability | `human_disagrees: true` | `HUMAN.REVIEWER_DISAGREEMENT` |
| AR regression | `dimension: "grounding_score", severity: "hard_fail"` | `REGRESS.GROUNDING_DROP` |
| AR regression | `dimension: "latency"` | `REGRESS.LATENCY_SPIKE` |

### CLI

```bash
# Report all classification records
python scripts/run_error_taxonomy_report.py --all

# Filter to a specific evaluation case
python scripts/run_error_taxonomy_report.py --case CASE_ID

# Filter to a specific artifact
python scripts/run_error_taxonomy_report.py --artifact ARTIFACT_ID
```

Output: `outputs/error_taxonomy_report.json` with counts by family, subtype,
source system, remediation target, and highest-impact subtypes.

---

## Auto-Failure Clustering (Prompt AV)

AV is the pattern detection layer that transforms raw `ErrorClassificationRecord`
objects (AU) into actionable, ranked failure pattern clusters for the prompt
improvement loop (AW).

### Clustering approach

AV uses **deterministic, threshold-driven clustering** — no opaque ML models,
no embeddings, no probabilistic groupings. Every clustering decision is
traceable to taxonomy codes.

Steps:

1. **Group by primary error code** — each record's highest-confidence error
   code determines its initial bucket.
2. **Sub-cluster by co-occurrence + pass_type** — within each primary-code
   group, records are further split by their full set of co-occurring codes
   and `pass_type` / `source_system` context.
3. **Merge small clusters** — groups below `min_cluster_size` (default: 2)
   are merged into the nearest sibling cluster sharing the same dominant
   error family, preserving all records.

Multi-label records (those with multiple `error_code` entries) are assigned
to the cluster whose `primary_error_code` matches their highest-confidence
code, ensuring every record belongs to exactly one cluster.

### Signature definition

Each cluster carries a `cluster_signature` derived entirely from taxonomy codes:

| Field | Definition |
|-------|-----------|
| `primary_error_code` | Most frequent error code across all records in the cluster |
| `secondary_error_codes` | Other codes that co-occur, sorted by descending frequency |
| `dominant_family` | Top-level family prefix of `primary_error_code` (e.g. `GROUND`) |

Signatures are computed deterministically; ties are broken alphabetically.

### Impact scoring

Impact is computed at two levels:

**Per-record** (`compute_weighted_severity`):
```
score = Σ (severity_weight × confidence)  for each classification entry
```

Default severity weights: `low=1`, `medium=2`, `high=3`, `critical=5`.

**Per-cluster** (`weighted_severity_score` in metrics):
```
cluster_score = Σ per-record scores  across all records in the cluster
```

Clusters are ranked by a three-key sort:
1. `weighted_severity_score` (descending)
2. `record_count` (descending)
3. `avg_confidence` (descending)

### Module location

```
spectrum_systems/modules/error_taxonomy/
    clustering.py       — ErrorCluster, ErrorClusterer
    impact.py           — compute_weighted_severity, rank_clusters
    cluster_store.py    — save_cluster, load_cluster, list_clusters
    cluster_pipeline.py — build_clusters_from_classifications, rank_and_filter_clusters
```

### Schema

| Schema | Purpose |
|--------|---------|
| `contracts/schemas/error_cluster.schema.json` | Governed cluster output format |

### Storage

Clusters are persisted as flat JSON under:
```
data/error_clusters/{cluster_id}.json
```

### How AV feeds AW

AV produces a ranked list of `ErrorCluster` objects. Each cluster exposes:

- `cluster_signature.primary_error_code` — the specific failure pattern
- `remediation_targets` — which system layer to fix (`prompt`, `grounding`,
  `retrieval`, `schema`, etc.)
- `metrics.weighted_severity_score` — relative priority
- `representative_examples` — concrete records AW can use as training signal

AW consumes this ranked list to determine:
- Which prompts to rewrite (clusters with `remediation_target = prompt`)
- Which grounding rules to tighten (clusters with `remediation_target = grounding`)
- Which retrieval pipeline to fix (clusters with `remediation_target = retrieval`)

### CLI

```bash
# Cluster all classification records
python scripts/run_error_clustering.py --all

# Filter to a specific evaluation case
python scripts/run_error_clustering.py --case CASE_ID
```

Output: `outputs/error_clusters.json` with full ranked cluster list.
