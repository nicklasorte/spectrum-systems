# HOP Golden Workflow (HOP-BATCH-1)

## Prompt type
BUILD

## Workflow
`transcript_control_input_signal` -> `faq_cluster_artifact`

## Input artifact type
- `transcript_control_input_signal`
- Required fields: deterministic transcript text, source metadata, trace identifier, and content hash.

## Output artifact type
- `faq_cluster_artifact`
- Required fields: grouped FAQ entries, deterministic ordering, source trace linkage, and output content hash.

## Evaluation criteria
1. **Schema validity:** input, run, score, and output artifacts validate against governed schemas.
2. **Determinism:** same input transcript and same candidate code produce byte-identical normalized output.
3. **Coverage:** candidate evaluated against golden, adversarial, and failure-derived eval cases.
4. **Trace completeness:** each run contains non-empty `trace.steps` and terminal status.
5. **Contract closure:** candidate cannot be admitted if interface/safety validation fails.

## Failure modes
- Missing required artifact fields (`artifact_id`, `schema_ref`, `trace`, `content_hash`).
- Candidate import/runtime failure.
- Eval dataset tampering or leakage signature detection.
- Missing trace step emission during execution.
- Output schema non-compliance for `faq_cluster_artifact` projection.

## Boundaries
- HOP does not grant promotion authority.
- HOP does not mutate candidates.
- HOP emits governed evidence only; control decisions remain external (EVL/TPA/CDE/SEL loop).
