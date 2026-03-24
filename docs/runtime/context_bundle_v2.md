# HS-06 Context Bundle v2 (Typed + Trusted)

## Purpose
Context Bundle v2 hardens the runtime input boundary by requiring every context item to be typed, trust-scoped, source-classified, provenance-linked, and deterministically ordered.

## Canonical artifact shape
Top-level required fields:
- `artifact_type` = `context_bundle`
- `schema_version` = `2.0.0`
- `context_bundle_id` and `context_id` (same deterministic ID)
- `created_at` (deterministic timestamp from canonical content seed)
- `trace.trace_id` and `trace.run_id` (runtime linkage)
- `context_items` (ordered typed items)

Compatibility fields retained in this slice:
- `primary_input`, `policy_constraints`, `retrieved_context`, `prior_artifacts`, `glossary_terms`, `unresolved_questions`
- `metadata`, `token_estimates`, `truncation_log`, `priority_order`

## Context item semantics
Each `context_items[]` entry is strict (`additionalProperties: false`) and includes:
- `item_index` (deterministic order index)
- `item_id` (deterministic stable ID)
- `item_type` (enum: `primary_input`, `policy_constraints`, `retrieved_context`, `prior_artifact`, `glossary_term`, `unresolved_question`)
- `trust_level` (enum: `high`, `medium`, `low`, `untrusted`)
- `source_classification` (enum: `internal`, `external`, `inferred`, `user_provided`)
- `provenance_refs` (non-empty references)
- `content`

## Composition and ordering rules
- Composition uses a fixed section order:
  1. primary_input
  2. policy_constraints
  3. retrieved_context (deterministically sorted)
  4. prior_artifact (deterministically sorted by artifact identity)
  5. glossary_term
  6. unresolved_question
- Same logical inputs produce the same `context_items` ordering, `context_bundle_id`, and `created_at`.
- No environment-dependent ordering behavior is allowed.

## Fail-closed behavior
Validation fails closed when any of the following is detected:
- unknown `item_type`
- unknown `trust_level`
- invalid `source_classification`
- missing/empty provenance references
- missing trace linkage (`trace_id` / `run_id`)
- non-sequential `item_index`
- malformed schema shape

No silent coercion is performed for unknown item type/trust/source values.

## Runtime linkage
At the AG seam (`agent_executor.construct_context_bundle`):
- input bundle is upgraded/composed to v2 when needed
- `trace.trace_id` and `trace.run_id` are injected from execution context
- validated bundle is used for execution and trace output

This guarantees execution artifacts can link directly to a governed context bundle identity.

## Explicitly out of scope in HS-06
- retrieval ranking redesign
- vector search infrastructure
- routing policy redesign
- prompt injection platform expansion
- broad memory/knowledge-graph platform work
