# Plan — CPL-04-FIX-STANDARDS-MANIFEST-SCOPE — 2026-04-27

## Prompt type
BUILD

## Roadmap item
CPL-04-FIX-STANDARDS-MANIFEST-SCOPE

## Objective
Keep CPL-04 implementation scoped to transcript-pipeline surfaces, explicitly block standards-manifest changes in scope guard coverage, and mark publication as pending SCH/GOV follow-up.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| tests/transcript_pipeline/test_cpl04_scope_guard.py | MODIFY | Block standards-manifest and other out-of-scope governance/NS paths for CPL-04 feature changes. |
| docs/review-actions/CPL-04_review.json | MODIFY | Mark publication status as pending SCH/GOV and record schema implementation completion language. |
| docs/review-actions/CPL-04_fix_actions.json | MODIFY | Record standards publication deferral and scope controls as follow-up actions. |
| docs/review-actions/PLAN-CPL-04-FIX-STANDARDS-MANIFEST-SCOPE-2026-04-27.md | CREATE | Document this bounded scope-fix plan. |

## Contracts touched
- None. `contracts/standards-manifest.json` publication update is deferred.

## Tests that must pass after execution
1. `python scripts/run_authority_shape_preflight.py --base-ref c660c4170f79f9dc68cba98132e504469256ebd3 --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
2. `python scripts/run_authority_leak_guard.py --base-ref c660c4170f79f9dc68cba98132e504469256ebd3 --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
3. `python scripts/run_system_registry_guard.py --base-ref c660c4170f79f9dc68cba98132e504469256ebd3 --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json`
4. `pytest tests/transcript_pipeline/test_cpl04_scope_guard.py`
5. `pytest tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py`
6. `pytest tests/transcript_pipeline/test_schemas_h01.py tests/transcript_pipeline/test_h01b_hardening.py`
7. `pytest tests/transcript_pipeline`

## Scope exclusions
- Do not modify `contracts/standards-manifest.json`.
- Do not modify governance/NS/lineage/observability modules.
- Do not weaken authority-shape or leak guards.
