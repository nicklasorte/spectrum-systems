# HS-07 Context Trust Segmentation

## Purpose
HS-07 hardens the HS-06 context boundary by making source class segmentation explicit, deterministic, and fail-closed. Runtime execution must never silently blend incompatible source classes.

## Source classification model
Each `context_items[]` entry uses a strict enum:
- `internal`
- `external`
- `inferred`
- `user_provided`

Each item must also carry:
- `trust_level`
- non-empty `provenance_refs`

### Item-type to source mapping (explicit, no implicit fallback)
- `primary_input` -> `user_provided`
- `policy_constraints` -> `internal`
- `retrieved_context` -> `external`
- `prior_artifact` -> `internal`
- `glossary_term` -> `internal`
- `unresolved_question` -> `inferred`

## Trust vs source relationship
Trust is constrained by source class:
- `internal`: `high|medium`
- `external`: `medium|low`
- `inferred`: `low|untrusted`
- `user_provided`: `high|medium|low|untrusted`

This prevents trust escalation by source reassignment and enforces explicit boundary semantics.

## Segmentation rules
`source_segmentation` is required on every context bundle and includes:
- `classification_order`
- `classification_counts`
- `item_refs_by_class`
- `grounded_item_refs`
- `inferred_item_refs`

Rules:
- internal and external content are kept separately by class-ref lists.
- inferred content is always segmented and never treated as grounded.
- user-provided content is separately segmented and does not inherit internal classification.
- no implicit classification or fallback assignment is allowed.

## Determinism
- context item ordering is deterministic (`item_index`).
- segmentation summaries are deterministic derivations of `context_items`.
- same logical input produces identical `context_bundle_id`, segmentation, and ordering.
- classification is rule-based only; no environment-sensitive paths.

## Fail-closed cases
Validation rejects bundles for:
- missing `source_classification`
- unknown classification value
- inconsistent `trust_level` vs `source_classification`
- inferred content presented as non-inferred (item-type/source mismatch)
- mixed-source rule violations
- segmentation summary mismatch vs item set
- missing provenance refs

## Runtime trace linkage
At AG runtime seam:
- validated `context_bundle` is required.
- `agent_execution_trace.context_bundle_id` links execution to bundle identity.
- `agent_execution_trace.context_source_summary` captures indirect class/item refs so outputs can be attributed by source class without duplicating full context payload.

## Out of scope
- retrieval system implementation
- ranking/search redesign
- vector DB integration
- routing or prompt architecture redesign
