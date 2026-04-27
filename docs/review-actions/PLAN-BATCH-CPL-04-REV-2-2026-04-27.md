# Plan — BATCH-CPL-04 (REV-2) — 2026-04-27

## Prompt type
BUILD

## Roadmap item
BATCH-CPL-04 (REV-2)

## Objective
Implement a deterministic meeting minutes extraction path that requires gate evidence, preserves source grounding, uses meeting_outcomes naming, and passes transcript pipeline validation checks.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/transcript_pipeline/meeting_minutes_artifact.schema.json | MODIFY | Replace legacy outcome shape with authority-safe meeting_outcomes schema and strict source grounding constraints. |
| contracts/standards-manifest.json | MODIFY | Bump published schema version metadata for meeting_minutes_artifact contract update. |
| contracts/examples/meeting_minutes_artifact.json | MODIFY | Align canonical example with updated meeting_minutes_artifact schema. |
| spectrum_systems/modules/transcript_pipeline/meeting_minutes_extractor.py | CREATE | Add deterministic CPL-04 extraction with strict gate checks and grounded markers only. |
| spectrum_systems/modules/transcript_pipeline/minutes_source_validation.py | CREATE | Add fail-closed source reference validation for outcomes and action items. |
| spectrum_systems/modules/transcript_pipeline/minutes_eval_helpers.py | CREATE | Add deterministic eval helper functions for grounding, completeness, and source coverage. |
| spectrum_systems/modules/transcript_pipeline/__init__.py | MODIFY | Export new CPL-04 module surfaces. |
| tests/transcript_pipeline/conftest.py | MODIFY | Update meeting_minutes fixture helper to new schema fields. |
| tests/transcript_pipeline/test_schemas_h01.py | MODIFY | Align meeting_minutes schema validation checks with meeting_outcomes shape. |
| tests/transcript_pipeline/test_h01b_hardening.py | MODIFY | Update source-grounding coverage tests to outcome naming and rules. |
| tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py | CREATE | Add CPL-04 deterministic extractor, gate, source, and PQX behavior tests. |
| tests/transcript_pipeline/fixtures/cpl04_valid_transcript.json | CREATE | Deterministic transcript fixture with explicit outcome/action markers. |
| tests/transcript_pipeline/fixtures/cpl04_no_outcomes_transcript.json | CREATE | Fixture with no explicit outcome markers to confirm no hallucination. |
| tests/transcript_pipeline/fixtures/cpl04_ambiguous_action_transcript.json | CREATE | Fixture with incomplete action info to verify unknown status behavior. |
| tests/transcript_pipeline/fixtures/cpl04_repeated_speaker_transcript.json | CREATE | Fixture to confirm attendee dedupe behavior. |
| docs/review-actions/CPL-04_review.json | CREATE | Authority-safe review artifact with review_signal/finding/recommendation shape. |
| docs/review-actions/CPL-04_fix_actions.json | CREATE | Authority-safe corrective action artifact for CPL-04 follow-up tracking. |

## Contracts touched
- `transcript_pipeline/meeting_minutes_artifact` (schema version update in schema and standards manifest).

## Tests that must pass after execution
1. `pytest tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py`
2. `pytest tests/transcript_pipeline/test_schemas_h01.py tests/transcript_pipeline/test_h01b_hardening.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `python scripts/run_authority_shape_preflight.py`
6. `python scripts/run_authority_leak_guard.py`
7. `python scripts/run_system_registry_guard.py`
8. `pytest tests/transcript_pipeline`

## Scope exclusions
- Do not change non-transcript-pipeline module behavior.
- Do not add routing logic.
- Do not add LLM-based extraction behavior.
- Do not modify unrelated contract schemas.

## Dependencies
- CPL-02 context bundle and CPL-03 gate evidence contracts remain authoritative inputs.
