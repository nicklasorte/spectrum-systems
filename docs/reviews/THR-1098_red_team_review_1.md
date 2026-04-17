# THR-1098 Red Team Review 1 — security / contracts / replay

## Scope
Transcript hardening execution surfaces: deterministic normalization, untrusted transcript admission, replay integrity, fail-closed behavior, and ownership boundary preservation.

## Severity ladder
- S0 informational
- S1 minor
- S2 required fix
- S3 block
- S4 halt

## Findings
1. **S2 — Untrusted transcript prompt-injection phrases were not quarantined in untrusted mode.**
   - Evidence: admission logic previously did not gate on instruction-surface tokens.
   - Fix: added `evaluate_context_admission` quarantine logic and fail-closed status on unsafe untrusted content.
   - Regression test: `test_thr1098_admission_route_judge_triage_counterfactual`.

2. **S2 — Material outputs could pass without evidence anchors in mixed output sets.**
   - Evidence: no strict ratio gate over material outputs.
   - Fix: added `enforce_evidence_coverage_gate_v2` with minimum anchor ratio and explicit blocking reasons.
   - Regression test: `test_thr1098_determinism_reconciliation_and_evidence_gate`.

3. **S1 — Determinism stress for reordered transcript lines was not explicitly exercised.**
   - Fix: added deterministic stress harness and ordering-variation test coverage.

## Closure
All S2+ findings fixed in this execution phase.
