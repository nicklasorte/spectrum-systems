# PLAN-WPG-PHASE-B-2026-04-15

## Prompt type
BUILD

## Scope
Implement **Phase B only** workflow loop for WPG/CRM:
meeting → transcript → minutes → actions → comments → resolution → revisions.

## Steps
1. Add new governed contract schemas and examples for WPG-31..34 and CRM-07..12, plus red-team findings fixture contract entries in the standards manifest.
2. Extend `spectrum_systems/orchestration/wpg_pipeline.py` and `scripts/run_wpg_pipeline.py` to ingest meeting artifact, generate minutes, extract/link actions, ingest and map comments, produce resolution/disposition/revision artifacts, and enforce fail-closed control decisions.
3. Add deterministic tests for each requested step file (`tests/test_wpg_meeting_artifact.py` … `tests/test_wpg_phase_b_regressions.py`) including red-team regression checks and full loop coverage.
4. Add review artifacts documenting RTX-11, RTX-12, and Phase-B validation outcome.
5. Run required contract and pipeline validation commands and fix regressions before commit.
