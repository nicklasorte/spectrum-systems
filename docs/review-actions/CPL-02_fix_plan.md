# CPL-02 — Context Bundle Assembly Fix Plan

- **Plan id:** `CPL02-FIX-PLAN`
- **Source review:** `RVA-CPL02-CONTEXT-001`
- **Batch:** `BATCH-CPL02`
- **Date:** 2026-04-27
- **Authority boundary:** Non-authority record. CDE retains decision authority; SEL retains compliance authority. This document records what was fixed and how it is locked, not a routing or release ruling.

## Goal

Close every S2+ finding from the CPL-02 red-team review in-batch with code patches and regression tests. S0/S1 hygiene findings closed for completeness.

## Fix index

| Fix id | Findings closed | Severity | Files touched | Regression tests |
|---|---|---|---|---|
| CPL02-FIX-001 | F-001 | S3 | `context_bundle_assembler.py`, `context_bundle.schema.json` | `TestReferentialIntegrity::test_missing_speaker_turns_fails`, `TestReferentialIntegrity::test_empty_speaker_turns_fails`, `TestSchemaAudit::test_schema_declares_segments_and_manifest_hash` |
| CPL02-FIX-002 | F-002 | S3 | `context_bundle_assembler.py` | `TestRedTeamRegressions::test_orphan_segment_blocked_by_referential_integrity_helper` |
| CPL02-FIX-003 | F-003 | S3 | `context_bundle_assembler.py` | `TestRedTeamRegressions::test_segment_drift_detected` |
| CPL02-FIX-004 | F-004 | S3 | `context_bundle_assembler.py` | `TestReplayDeterminism::test_reordering_segments_changes_manifest_hash`, `TestRedTeamRegressions::test_artifact_id_changes_when_content_changes` |
| CPL02-FIX-005 | F-005 | S2 | `context_bundle_assembler.py` | `TestRedTeamRegressions::test_count_mismatch_detected` |
| CPL02-FIX-006 | F-006, F-007 | S2 | `context_bundle_assembler.py` | `TestReferentialIntegrity::test_duplicate_turn_id_fails`, `TestRedTeamRegressions::test_duplicate_segment_id_detected` |
| CPL02-FIX-007 | F-008 | S2 | `context_bundle_assembler.py`, `tests/...` | `TestPQXIntegration::test_assembler_cannot_write_artifact_directly`, `TestPQXIntegration::test_assembly_via_pqx_registers_artifact` |
| CPL02-FIX-008 | F-009 | S2 | `context_bundle_assembler.py` | `TestReplayDeterminism::test_manifest_hash_independent_of_envelope`, `TestReplayDeterminism::test_content_hash_is_replay_stable` |
| CPL02-FIX-009 | F-010, F-011 | S1 | `context_bundle_assembler.py` | `TestReferentialIntegrity::test_invalid_trace_id_fails`, `TestReferentialIntegrity::test_invalid_span_id_fails`, `TestReferentialIntegrity::test_invalid_artifact_type_fails`, `TestReferentialIntegrity::test_invalid_source_artifact_id_fails` |
| CPL02-FIX-010 | F-012 | S0 | `context_bundle_assembler.py` | n/a (docstring contract) |

## Hard rules preserved

- No LLM. No summarization. No routing.
- Assembler does not write artifacts; PQX does.
- `manifest_hash` is segment-only. `content_hash` is envelope-wide minus volatile fields. Both are deterministic.
- Schema enforces `additionalProperties: false` on the bundle and on every segment.

## Validation

Run:

```
pytest tests/transcript_pipeline -q
python scripts/run_3ls_authority_preflight.py --base-ref origin/main --head-ref HEAD
python scripts/run_authority_leak_guard.py --base-ref origin/main --head-ref HEAD
python scripts/run_system_registry_guard.py --base-ref origin/main --head-ref HEAD
```

All must pass before promotion.

## Remaining risk (carried, not closed)

- Eval gate (CPL-03) is not yet wired. Until CPL-03 lands, downstream consumers must treat the bundle as input-only and rely on CDE for any decision over admission.
- Non-`txt` source formats are accepted by the H08 schema but parsed only as `txt` today. CPL-02 inherits this constraint and assumes 1:1 alignment with `speaker_turns`. New parsers must come with their own CPL-02 regression suite.
