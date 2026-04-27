# CPL-04 — Meeting Minutes Extractor Fix Plan

- **Plan id:** `CPL04-FIX-PLAN`
- **Source review:** `RVA-CPL04-MINUTES-001`
- **Batch:** `BATCH-CPL-04`
- **Date:** 2026-04-27
- **Authority boundary:** Non-authority record. Canonical routing remains with the appropriate canonical owner. This document records what was fixed and how it is locked; it is not a routing or release-readiness signal.

## Goal

Close every S2+ finding from the CPL-04 red-team review in-batch with code patches, schema updates, and regression tests. S0/S1 hygiene findings closed for completeness.

## Fix index

| Fix id | Findings closed | Severity | Files touched | Regression tests |
|---|---|---|---|---|
| CPL04-FIX-001 | F-001 | S3 | `meeting_minutes_artifact.schema.json`, `meeting_minutes_extractor.py`, `meeting_minutes_evals.py` | `TestSchemaAudit::test_decision_without_refs_or_rationale_fails`, `TestRedTeamRegressions::test_hallucinated_decision_blocked_by_schema`, `TestEvalHelpers::test_decision_grounding_flags_unbacked_decision` |
| CPL04-FIX-002 | F-002 | S3 | `meeting_minutes_artifact.schema.json`, `meeting_minutes_extractor.py`, `meeting_minutes_evals.py` | `TestSchemaAudit::test_action_item_requires_explicit_unknown_when_assignee_missing`, `TestSchemaAudit::test_action_item_requires_explicit_unknown_when_due_date_missing`, `TestSchemaAudit::test_action_item_with_explicit_unknowns_passes`, `TestEvalHelpers::test_action_item_completeness_flags_missing_status`, `TestDeterministicExtraction::test_action_items_have_explicit_unknown_when_assignee_missing` |
| CPL04-FIX-003 | F-003 | S3 | `minutes_source_validation.py`, `meeting_minutes_extractor.py` | `TestSourceGrounding::test_fake_source_turn_id_rejected`, `TestSourceGrounding::test_fake_source_segment_id_rejected`, `TestEvalHelpers::test_source_grounding_flags_fake_turn` |
| CPL04-FIX-004 | F-004 | S3 | `minutes_source_validation.py`, `meeting_minutes_artifact.schema.json` | `TestSourceGrounding::test_mismatched_source_pair_rejected` |
| CPL04-FIX-005 | F-005 | S3 | `minutes_source_validation.py`, `meeting_minutes_extractor.py` | `TestSourceGrounding::test_line_index_drift_rejected`, `TestSourceGrounding::test_segment_line_index_drift_rejected_at_extract_time` |
| CPL04-FIX-006 | F-006 | S3 | `meeting_minutes_extractor.py` | `TestGateEvidenceChecks::test_failed_gate_rejected`, `TestGateEvidenceChecks::test_missing_gate_rejected`, `TestGateEvidenceChecks::test_conditional_gate_rejected`, `TestGateEvidenceChecks::test_missing_eval_summary_id_rejected`, `TestGateEvidenceChecks::test_target_artifact_ids_mismatch_rejected`, `TestGateEvidenceChecks::test_empty_target_artifact_ids_rejected` |
| CPL04-FIX-007 | F-007 | S3 | `meeting_minutes_extractor.py` | `TestPQXIntegration::test_payload_has_no_content_hash_before_pqx`, `TestPQXIntegration::test_pqx_registers_artifact_and_emits_record`, `TestPQXIntegration::test_direct_artifact_store_write_rejected` |
| CPL04-FIX-008 | F-008 | S2 | `meeting_minutes_extractor.py` | `TestGateEvidenceChecks::test_bundle_source_link_mismatch_rejected` |
| CPL04-FIX-009 | F-009 | S2 | `meeting_minutes_extractor.py` | `TestDeterministicExtraction::test_provider_adapter_mode_requires_adapter`, `TestRedTeamRegressions::test_no_provider_adapter_in_default_path` |
| CPL04-FIX-010 | F-010 | S1 | `minutes_source_validation.py` | `TestSourceGrounding::test_source_coverage_mismatch_rejected` |
| CPL04-FIX-011 | F-011 | S0 | `meeting_minutes_extractor.py`, `minutes_source_validation.py`, `meeting_minutes_artifact.schema.json`, `docs/reviews/CPL-04_meeting_minutes_review.md`, `contracts/review_artifact/CPL-04_review.json` | `TestRedTeamRegressions::test_authority_safe_vocabulary_in_module` |

## Hard rules preserved

- No live LLM/API calls in tests.
- No free-form output escaping the schema. Every claim is bound to a (turn, segment, line_index) source ref.
- Pure extractor does not register artifacts; `run_meeting_minutes_extraction_via_pqx` does.
- `meeting_minutes_artifact` is linked to its admission evidence by id (`gate_evidence_id` and `eval_summary_id` echo the gate evidence supplied at admission). Both ids must reach `extract_meeting_minutes` together.
- Fail-closed admission:
  - `gate_status != passed_gate` → `MeetingMinutesExtractionError(GATE_NOT_PASSED)`
  - `target_artifact_ids` does not include both transcript and bundle ids → `GATE_TARGET_MISMATCH`
  - missing or malformed `eval_summary_id` → `MISSING_EVAL_SUMMARY_ID`
  - bundle does not link to the supplied transcript → `BUNDLE_SOURCE_LINK_MISMATCH`
  - any segment drifts in `line_index` → `SEGMENT_LINE_INDEX_DRIFT`
- Schema requires `additionalProperties: false` on every envelope and every `agenda_item` / `decision_record` / `action_item` / `source_ref` / `source_coverage` entry.
- `extraction_mode="provider_adapter"` requires an explicit adapter callable; tests never wire one and no live network egress occurs.

## Validation

Run:

```
pytest tests/transcript_pipeline -q
python scripts/run_3ls_authority_preflight.py --base-ref origin/main --head-ref HEAD
python scripts/run_authority_shape_preflight.py \
  --base-ref origin/main \
  --head-ref HEAD \
  --suggest-only \
  --output outputs/authority_shape_preflight/authority_shape_preflight_result.json
python scripts/run_authority_leak_guard.py \
  --base-ref origin/main \
  --head-ref HEAD \
  --output outputs/authority_leak_guard/authority_leak_guard_result.json
python scripts/run_system_registry_guard.py \
  --base-ref origin/main \
  --head-ref HEAD \
  --output outputs/system_registry_guard/system_registry_guard_result.json
```

All must pass before advancement to the next-stage readiness signal.

## Remaining risk (carried, not closed)

- The deterministic extractor uses bounded marker matching ("decision:", "we decided", "agreed to", "action:", "todo:", "will follow up", "assigned to", "agenda:" / "agenda item:" / "first item" / "next item" / "today we are" / "today we will"). Real-world transcripts may use other phrasings. CPL-08 will pick this up by introducing a governed adoption flow for new markers; nothing routes around the schema in the meantime.
- Provider-adapter mode remains a stub. Any future live adapter must come with its own admission evidence, its own red-team review, and the same source-ref validator that grounds deterministic output today.
- Bulk extraction over a corpus is out of scope for CPL-04 and will need its own coverage when CPL-05 issues the next-stage extractor.
- Callers that assemble dicts outside the governed path are responsible for using `run_meeting_minutes_extraction_via_pqx`. The artifact store rejects direct registration attempts because the pure payload carries no `content_hash`.
