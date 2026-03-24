# HS-09 Evidence Binding + Citation System

HS-09 adds deterministic post-finalization evidence binding to HS-08.
After the final pass output is produced, important claims are extracted,
classified, and linked to governed evidence/source references.

## Claim classification model

Each bound claim is assigned exactly one classification:

- `directly_supported`
  - Claim has one or more valid `evidence_item_refs`.
- `inferred`
  - Claim has no direct evidence refs and is marked as an inference.
- `unsupported`
  - Claim has neither direct evidence refs nor inference linkage.

The classification enum is closed and deterministic.

## Evidence linkage rules

For each claim, HS-09 records:

- `claim_id`
- `claim_path`
- `claim_text`
- `claim_classification`
- `evidence_item_refs`
- `source_artifact_refs`
- `inferred_from_claim_ids`
- `pass_id`, `trace_id`, `pass_output_ref`

`evidence_item_refs` must resolve to `context_bundle.context_items[*].item_id`.
`source_artifact_refs` must resolve to known source artifacts in the validated bundle.
No claim can be `directly_supported` with zero evidence refs.

## Bounded claim extraction

HS-09 intentionally uses a narrow deterministic extraction surface:

1. `final_output.claims[*]` (if present)
2. Non-empty top-level text fields:
   - `summary`
   - `decision`
   - `recommendation`
   - `conclusion`

No semantic/fuzzy claim mining is performed in this slice.

## Fail-closed behavior

Binding fails closed when:

- required-grounded mode sees any `inferred` or `unsupported` claim
- a `directly_supported` claim has no evidence refs
- evidence refs point to unknown context item refs
- source artifact refs are unknown
- explicit claim classification conflicts with derived classification
- inference links point to unknown claim IDs
- generated binding artifact fails contract validation

Policy modes are explicit and traceable:

- `required_grounded`
- `allow_inferred`
- `allow_unsupported`

## Runtime trace linkage

- `multi_pass_generation_record` includes `evidence_binding`:
  - `record_id`
  - `policy_mode`
  - `claim_ids`
- `agent_execution_trace.multi_pass_generation` includes:
  - `evidence_binding_record_id`
  - `evidence_binding_claim_ids`
  - `evidence_binding_policy_mode`

This allows deterministic reconstruction without payload duplication.

## Out of scope

HS-09 does **not** implement:

- citation rendering/formatting styles
- academic bibliography systems
- fuzzy attribution or semantic retrieval redesign
- UI/document rendering features
