# RAX-HARDEN-READINESS-03 Design Note

## Prompt type
BUILD

## Summary
RAX control-readiness is now a mandatory gate. Advancement is fail-closed unless a valid `rax_control_readiness_record` exists and explicitly indicates `ready_for_control=true`, `decision=ready`, and no blocking reasons.

## Governed recomputation
Readiness is now recomputed from governed inputs and not trusted from caller-declared summaries. The computation consumes:
- required eval policy + eval results
- eval summary consistency checks
- assurance/audit evidence
- trace linkage/completeness evidence
- lineage/provenance validity evidence
- dependency graph integrity and resolution state
- baseline regression and cross-run replay consistency signals

## Mandatory readiness inputs
Readiness now requires all of the following to remain ready:
- trace linkage and trace completeness
- lineage validity
- immutable authority evidence presence and no authority drift failure signals
- dependency graph integrity with no unresolved dependencies
- contradiction-free eval/readiness signals

Any critical failure or contradiction forces `ready_for_control=false`, `decision!=ready`, and populated `blocking_reasons`.
