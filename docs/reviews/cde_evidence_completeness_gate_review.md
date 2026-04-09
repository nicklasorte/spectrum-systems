# CDE Evidence Completeness + Certification Gate Review

## Scope
BATCH-SYS-ENF-04 hardening for CDE and promotion consumers, focused on fail-closed evidence completeness.

## Evidence now required for promotable CDE outcomes
A promotable (`decision_type=lock`) CDE outcome now requires governed evidence inputs for:
- `eval_summary_ref`
- complete required eval coverage (`required_eval_ids` + `required_eval_results`, or explicit completeness rollup)
- no failed required eval status
- no indeterminate/unknown required eval status
- non-placeholder trace continuity (`trace_id`, `trace_artifact_refs`, optional `trace_ids` continuity check)
- certification evidence when promotion requires certification (`certification_ref` + passing `certification_status`)
- policy-modeled replay consistency refs when required

When any required evidence is incomplete, CDE converts would-be promotable outcomes to `blocked` and emits explicit fail-closed reason codes.

## Fail-open paths closed
Closed paths in this batch:
1. **Lock from partial eval evidence**: missing eval summary/required eval results now blocks.
2. **Indeterminate required eval treated as pass**: now blocks promotable path.
3. **Weak trace placeholders on promotable path**: now blocks.
4. **Missing certification on promotable path**: now blocks.
5. **Promotion consumer artifact-exists assumption**: downstream now requires promotable CDE decision + evidence-complete signal.
6. **Canonical promoted transition accepted non-lock CDE states**: promotion now requires `decision_type=lock` plus evidence-complete reason-code set and governed evidence refs.

## Certification integration status
**Partially wired (strict-gated)**.

What is fully true now:
- CDE promotable path requires certification reference and passing status signal.
- Sequence promotion gate and promotion decision artifact both fail closed when certification completeness evidence is missing from CDE and trust-spine inputs.

What is still partial:
- GitHub continuation currently does not yet ingest full eval/certification artifacts from RIL/TLC outputs in all paths; therefore promotable outcomes are intentionally blocked unless complete governed evidence is supplied.

## Remaining gaps before full GOV-10-grade rigor
- End-to-end ingestion wiring of governed eval summary/result and done-certification artifacts into the GitHub continuation adapter.
- Strong schema-level encoding for CDE evidence completeness dimensions (evidence/certification completeness booleans) if contract governance authorizes additive versioning.
- Replay consistency requirement mapping should be driven directly by policy artifacts for all runtime paths (currently bounded hook exists).
- Additional integration tests for complete positive promotion paths once ingestion pipeline includes all governed evidence artifacts.
