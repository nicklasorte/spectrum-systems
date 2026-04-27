# CPL-04 — Meeting Minutes Extractor Red-Team Review

- **Review id:** `RVA-CPL04-MINUTES-001`
- **Reviewer:** `ARA-CPL04`
- **Reviewed batch:** `BATCH-CPL-04`
- **Review signal:** `revision_recommended` (all S2+ findings closed in-batch — see `CPL-04_fix_actions.json`)
- **Authority boundary:** Non-authority review signal. Canonical routing remains with the appropriate canonical owner. The meeting_minutes_artifact records evidence only — no routing or release advancement signal is implied.
- **Date:** 2026-04-27

## Scope

Adversarial review of the CPL-04 meeting minutes extraction path:

- `contracts/schemas/transcript_pipeline/meeting_minutes_artifact.schema.json`
- `spectrum_systems/modules/transcript_pipeline/meeting_minutes_extractor.py`
- `spectrum_systems/modules/transcript_pipeline/minutes_source_validation.py`
- `spectrum_systems/modules/transcript_pipeline/meeting_minutes_evals.py`
- Consumer-side checks only on `pqx_step_harness.py`, `artifact_store.py`, and the upstream H08/CPL-02/CPL-03 producers.

## Attack surface

| Vector | What we tried |
|---|---|
| Hallucinated decisions | Inject a decision row with no `source_refs` and no `rationale`. |
| Hallucinated agenda items | Inject an agenda row with no `source_refs`. |
| Source-ref-free action items | Inject an action item without `source_refs`, with `assignee_status` / `due_date_status` set to `unknown`. |
| Fake source_turn_id | Replace a real ref with a turn id that does not exist in `transcript.speaker_turns`. |
| Fake source_segment_id | Replace a real ref with a segment id that does not exist in `context_bundle.segments`. |
| Mismatched source pair | Pair a real `source_turn_id` with a real but unrelated `source_segment_id`. |
| line_index drift | Keep both ids real but swap `line_index` to a stale or wrong value. |
| Gate evidence bypass | Submit `failed_gate`, `missing_gate`, `conditional_gate`, or strip `eval_summary_id` / `target_artifact_ids`. |
| Bundle source link bypass | Hand a `context_bundle` that links to a different transcript than the one supplied. |
| Direct artifact write | Bypass PQX and pass a payload to `ArtifactStore.register_artifact` with no harness-minted hash. |
| Provider-mode covert egress | Request `extraction_mode="provider_adapter"` without any adapter wired in (looking for silent network calls). |
| Schema escape | Inject extra top-level fields, omit `source_coverage`, or smuggle floats into integer fields. |
| Authority leak | Scan module text and schema descriptions for forbidden authority verbs. |

## Findings (severity ladder S0–S4)

| ID | Severity | Description | Recommendation | Blocking |
|---|---|---|---|---|
| F-001 | S3 | A decision row with no `source_refs` and no `rationale` could surface a hallucinated finding while satisfying the legacy schema (only `decision_id` + `description` were required). | Schema decision_record `anyOf [source_refs, rationale]` and `additionalProperties: false`; `eval_decision_grounding` re-checks the same invariant; deterministic extractor only emits decisions on explicit markers and always pins `source_refs`. | yes |
| F-002 | S3 | An action item could omit `assignee` and `due_date` entirely, masking unknown ownership as a normalized output. | Schema requires `assignee` or `assignee_status="unknown"` AND `due_date` or `due_date_status="unknown"`; `eval_action_item_completeness` re-checks; deterministic extractor sets the explicit status when no marker resolves. | yes |
| F-003 | S3 | Forged `source_refs` with a fake `source_turn_id` or `source_segment_id` could pass schema validation by satisfying patterns alone. | `validate_minutes_source_refs` indexes both real corpora and rejects `FAKE_SOURCE_TURN_ID` / `FAKE_SOURCE_SEGMENT_ID`; the extractor calls the validator before returning so no extractor path can emit fake refs. | yes |
| F-004 | S3 | A `source_ref` could pair a real `source_turn_id` with a real but unrelated `source_segment_id`, splitting the evidence trail. | Validator cross-checks `segment.source_turn_id == ref.source_turn_id`; raises `SOURCE_PAIR_MISMATCH`. Schema docstrings call out the invariant. | yes |
| F-005 | S3 | `line_index` drift could keep both ids real but bind to a wrong line, breaking replay. | Validator raises `LINE_INDEX_DRIFT` when `ref.line_index != turn.line_index`; extractor checks segment-vs-turn alignment up front and raises `SEGMENT_LINE_INDEX_DRIFT` if the bundle itself is tampered. | yes |
| F-006 | S3 | Gate evidence bypass: a caller with a `failed_gate`, `missing_gate`, `conditional_gate`, malformed `target_artifact_ids`, or missing `eval_summary_id` could trigger extraction. | `_validate_gate_evidence` requires `gate_status == passed_gate`, both transcript and bundle ids in `target_artifact_ids`, and a non-empty `eval_summary_id`; raises `GATE_NOT_PASSED`, `MISSING_GATE_TARGET_IDS`, `GATE_TARGET_MISMATCH`, or `MISSING_EVAL_SUMMARY_ID`. | yes |
| F-007 | S3 | Direct artifact write: a caller could hand the extractor's payload to `ArtifactStore.register_artifact` and skip PQX, losing `pqx_execution_record` emission and trace propagation. | Pure function returns payloads WITHOUT `content_hash`; the store rejects direct registration; `run_meeting_minutes_extraction_via_pqx` is the only sanctioned write path. Test `test_direct_artifact_store_write_rejected` locks the contract. | yes |
| F-008 | S2 | A bundle whose `source_artifact_id` does not match the supplied transcript could be paired by mistake, breaking lineage. | Extractor raises `BUNDLE_SOURCE_LINK_MISMATCH` before any extraction work runs. | yes |
| F-009 | S2 | A caller could request `extraction_mode="provider_adapter"` expecting a transparent live call. | Extractor raises `PROVIDER_ADAPTER_UNAVAILABLE` when no explicit adapter is supplied. No tests wire a live adapter; no network egress occurs in tests. | yes |
| F-010 | S1 | `source_coverage` could be silently fabricated to overstate evidence breadth. | `validate_minutes_source_refs` recomputes `total_turns / referenced_turns / referenced_segments` and raises `SOURCE_COVERAGE_MISMATCH` on drift. | no |
| F-011 | S0 | Module docstrings could omit the evidence-only boundary statement, risking misreading the artifact as a routing signal. | Module docstring and schema `description` fields state the evidence-only role; review artifacts use authority-safe vocabulary; the test suite includes `test_authority_safe_vocabulary_in_module`. | no |

No S4 findings.

## Outcome

All S2+ findings closed in-batch with code + regression tests. See:

- `contracts/review_actions/CPL-04_fix_actions.json`
- `docs/review-actions/CPL-04_fix_plan.md`
- `tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py::TestSchemaAudit`
- `tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py::TestGateEvidenceChecks`
- `tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py::TestDeterministicExtraction`
- `tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py::TestSourceGrounding`
- `tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py::TestPQXIntegration`
- `tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py::TestEvalHelpers`
- `tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py::TestRedTeamRegressions`

## Authority-shape posture

This review uses authority-safe vocabulary throughout. The reserved authority verbs listed in `contracts/governance/authority_shape_vocabulary.json` do not appear in either the module text under review or this document. The eval helpers and review artifacts validate, require, and check; canonical routing or advancement remains with the appropriate canonical owner.
