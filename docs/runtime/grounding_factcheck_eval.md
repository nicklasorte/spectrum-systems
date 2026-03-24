# HS-19 Grounding + Fact-Check Eval Layer

## Purpose
HS-19 introduces a deterministic, governed eval artifact that runs after HS-09 evidence binding and evaluates whether bound claims remain supportable under explicit bounded rules.

This layer is intentionally narrow:
- no probabilistic scoring
- no open-ended model judging
- no online verification
- deterministic outputs for same inputs

## Artifact contract
- Schema: `contracts/schemas/grounding_factcheck_eval.schema.json`
- Example: `contracts/examples/grounding_factcheck_eval.json`
- Manifest key: `grounding_factcheck_eval`

Core fields:
- `artifact_type`, `schema_version`, `eval_id`, `created_at`
- `source_artifact_id`, `evidence_binding_record_id`
- `overall_status`, `failure_classes`
- `claim_results`
- `trace_linkage`
- `policy`

## Failure classes (bounded enum)
Only the following classes are allowed:
- `fact_check_fail`
- `semantic_error`
- `evidence_mismatch`
- `unsupported_grounded_claim`
- `incomplete_grounding`

No free-form classes are emitted.

## Claim-level eval semantics
For each HS-09 bound claim, HS-19 records:
- `claim_id`
- `claim_classification_from_binding`
- `eval_status` (`pass` | `warn` | `fail`)
- `failure_classes` (bounded enum list)
- `supporting_evidence_refs_checked`
- `rationale_code` (bounded deterministic code)

Deterministic checks:
1. **Directly supported checks**
   - Must include valid evidence refs.
   - Evidence refs must resolve to context items.
   - Claim text must have lexical overlap with resolved evidence content.
2. **Inferred claim integrity**
   - Inferred claims remain inferred.
   - Inferred claims with direct evidence refs are flagged as mismatch.
3. **Unsupported claim policy handling**
   - Unsupported claims are surfaced and controlled by explicit policy booleans.
4. **Grounded-required enforcement**
   - If policy disallows inferred/unsupported claims, those claims fail with explicit classes.
5. **Bounded semantic checks**
   - When claim payload includes `canonical_term_refs`, refs must be selected glossary entries.
   - Canonical term text must appear in claim text when ref is present.

## Policy behavior
`GroundingFactCheckPolicy`:
- `required` (default `true`)
- `allow_inferred_claims` (default `false`)
- `allow_unsupported_claims` (default `false`)
- `fail_on_fact_check_fail` (default `true`)

Integration default in multi-pass runtime is conservative and deterministic.

## Fail-closed cases
Runtime fails closed for:
- malformed eval artifact (schema validation failure)
- missing evidence binding inputs
- invalid claim refs/classification state
- inconsistent eval state (`overall_status=pass` with failure classes)
- policy requires eval but eval did not run

## Runtime trace linkage
HS-19 emits linkage in:
- `multi_pass_generation_record.grounding_factcheck_eval`
  - `eval_id`
  - `overall_status`
  - `failure_classes`
- `agent_execution_trace.multi_pass_generation`
  - `grounding_factcheck_eval_id`
  - `grounding_factcheck_overall_status`
  - `grounding_factcheck_failure_classes`

The full HS-19 artifact carries trace refs to reconstruct evaluated claims, checked evidence refs, and deterministic failure reasons.

## Out of scope
- General-purpose LLM judge frameworks
- Retrieval or context segmentation redesign
- External fact checking or web lookup
- Broad eval platform orchestration
