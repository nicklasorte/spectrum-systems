# Plan — CPL-04-FIX-CONTRACT-NAMESPACE — 2026-04-27

## Prompt type
BUILD

## Roadmap item
CPL-04-FIX-CONTRACT-NAMESPACE

## Objective
Restore the legacy WPG root example, move the CPL-04 example into transcript_pipeline namespace, and add regression coverage proving both namespaces validate independently.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| contracts/examples/meeting_minutes_artifact.json | MODIFY | Restore legacy WPG example contract shape used by WPG tests. |
| contracts/examples/transcript_pipeline/meeting_minutes_artifact.example.json | CREATE | Add namespaced CPL-04 transcript-pipeline example payload (schema v1.1.0). |
| tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py | MODIFY | Validate namespaced CPL example and assert extractor output schema_ref; avoid root WPG example dependency. |
| tests/transcript_pipeline/test_schemas_h01.py | MODIFY | Add namespace regression assertions for root WPG and transcript_pipeline examples. |
| tests/transcript_pipeline/conftest.py | MODIFY (if needed) | Keep fixture shape aligned with transcript_pipeline schema surface. |
| docs/review-actions/CPL-04_fix_actions.json | MODIFY | Record namespace split follow-up action with publication still pending. |
| docs/review-actions/PLAN-CPL-04-FIX-CONTRACT-NAMESPACE-2026-04-27.md | CREATE | Plan artifact for this multi-file scope fix. |

## Contracts touched
- None (schema already at transcript_pipeline/meeting_minutes_artifact v1.1.0; this change is example namespace alignment only).

## Tests that must pass after execution
1. `python scripts/run_authority_shape_preflight.py --base-ref c660c4170f79f9dc68cba98132e504469256ebd3 --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
2. `python scripts/run_authority_leak_guard.py --base-ref c660c4170f79f9dc68cba98132e504469256ebd3 --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
3. `python scripts/run_system_registry_guard.py --base-ref c660c4170f79f9dc68cba98132e504469256ebd3 --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json`
4. `pytest tests/test_wpg_contracts.py::test_wpg_examples_validate`
5. `pytest tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py`
6. `pytest tests/transcript_pipeline/test_schemas_h01.py tests/transcript_pipeline/test_h01b_hardening.py`
7. `pytest tests/transcript_pipeline`
8. `pytest`

## Scope exclusions
- Do not modify `contracts/standards-manifest.json`.
- Do not weaken WPG contract validation.
- Do not modify governance/NS/lineage/observability surfaces.
- Do not weaken authority guards.
