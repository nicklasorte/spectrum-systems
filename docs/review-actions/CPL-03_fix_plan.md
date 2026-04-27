# CPL-03 — Transcript / Context Eval Gate Fix Plan

- **Plan id:** `CPL03-FIX-PLAN`
- **Source review:** `RVA-CPL03-EVALGATE-001`
- **Batch:** `BATCH-CPL-03`
- **Date:** 2026-04-27
- **Authority boundary:** Non-authority record. Canonical routing remains with the appropriate canonical owner. This document records what was fixed and how it is locked; it is not a routing or release-readiness signal.

## Goal

Close every S2+ finding from the CPL-03 red-team review in-batch with code patches and regression tests. S0/S1 hygiene findings closed for completeness.

## Fix index

| Fix id | Findings closed | Severity | Files touched | Regression tests |
|---|---|---|---|---|
| CPL03-FIX-001 | F-001 | S3 | `eval_gate.py`, `tests/...test_eval_gate_cpl03.py` | `TestPQXIntegration::test_runs_two_steps_and_registers_both_artifacts`, `TestPQXIntegration::test_pqx_summary_and_evidence_share_trace`, `TestRedTeamRegressions::test_F001_fake_gate_evidence_rejected_by_back_reference_drift` |
| CPL03-FIX-002 | F-002 | S3 | `eval_gate.py` | `TestFailClosedGate::test_manifest_hash_mismatch`, `TestRedTeamRegressions::test_F002_replay_mismatch_lands_in_failed_gate`, `TestNegativeMatrix::test_mutation_lands_in_failed_gate` |
| CPL03-FIX-003 | F-003 | S3 | `eval_gate.py` | `TestFailClosedGate::test_partial_coverage_fails`, `TestFailClosedGate::test_extra_segment_fails_coverage`, `TestRedTeamRegressions::test_F003_partial_coverage_lands_in_failed_gate` |
| CPL03-FIX-004 | F-004 | S3 | `eval_gate.py`, `tests/...test_eval_gate_cpl03.py` | `TestEvaluator::test_evaluator_returns_no_content_hash`, `TestPQXIntegration::test_evaluator_cannot_register_directly_without_pqx`, `TestRedTeamRegressions::test_F004_pqx_bypass_attempt_blocked`, `TestAuthorityShapeVocabulary::test_eval_gate_module_has_no_register_artifact_call` |
| CPL03-FIX-005 | F-005 | S2 | `gate_evidence.schema.json` | `TestGateEvidenceSchemaAudit::test_schema_required_fields`, `TestGateEvidenceSchemaAudit::test_eval_summary_id_pattern`, `TestRedTeamRegressions::test_F005_missing_eval_summary_id_in_gate_rejected_by_schema` |
| CPL03-FIX-006 | F-006 | S2 | `eval_gate.py` | `TestFailClosedGate::test_fake_source_turn_id`, `TestFailClosedGate::test_segment_drift_detected` |
| CPL03-FIX-007 | F-007 | S1 | `eval_summary.schema.json`, `eval_gate.py` | `TestEvalSummarySchemaAudit::test_schema_overall_status_enum`, `TestEvalSummarySchemaAudit::test_schema_eval_result_required`, `TestRedTeamRegressions::test_F007_eval_with_undefined_status_rejected_by_schema`, `TestRedTeamRegressions::test_F008_unknown_gate_status_rejected_by_schema` |
| CPL03-FIX-008 | F-008 | S0 | `eval_gate.py`, `eval_summary.schema.json`, `gate_evidence.schema.json` | `TestAuthorityShapeVocabulary::test_eval_gate_module_has_no_authority_vocabulary`, `TestAuthorityShapeVocabulary::test_eval_summary_schema_has_no_authority_vocabulary`, `TestAuthorityShapeVocabulary::test_gate_evidence_schema_has_no_authority_vocabulary` |

## Hard rules preserved

- No LLM. No routing logic. No authority vocabulary.
- Pure evaluator does not register artifacts; `run_eval_gate_via_pqx` does.
- `eval_summary` and `gate_evidence` are linked by id (`gate_evidence.eval_summary_id == eval_summary.artifact_id`); the link is verified deterministically inside the PQX wrapper.
- Fail-closed gate logic:
  - any eval fails → `failed_gate`
  - any required eval missing → `missing_gate`
  - all pass → `passed_gate`
  - indeterminate → `conditional_gate` (NOT routable)
- Schema requires `additionalProperties: false` on every envelope and on every `eval_result` entry.

## Validation

Run:

```
pytest tests/transcript_pipeline -q
python scripts/run_3ls_authority_preflight.py --base-ref origin/main --head-ref HEAD
python scripts/run_authority_leak_guard.py --base-ref origin/main --head-ref HEAD
python scripts/run_system_registry_guard.py --base-ref origin/main --head-ref HEAD
```

All must pass before advancement to the next-stage readiness signal.

## Remaining risk (carried, not closed)

- Bulk eval surfaces (corpus-level) are out of scope and must come with their own regression suite.
- `conditional_gate` is reachable only from indeterminate aggregations; the runtime never produces it today. The schema allows it for future eval extensions; the `routable` flag stays `false` in that case.
- Callers that assemble dicts outside the governed path are responsible for using `run_eval_gate_via_pqx`. The artifact store rejects direct registration attempts because the pure payload carries no `content_hash`.
