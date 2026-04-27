# Plan — CPL-04-FIX-SCOPE-AUTHORITY — 2026-04-27

## Prompt type
BUILD

## Roadmap item
CPL-04-FIX-SCOPE-AUTHORITY

## Objective
Rescope CPL-04 changes to transcript-pipeline artifacts only, remove out-of-scope authority-scan triggers, and keep CPL-04 extractor/runtime behavior and tests passing.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| contracts/standards-manifest.json | MODIFY | Revert CPL-04 manifest edit so authority-shape preflight does not scan global governance vocabulary in this scoped PR. |
| tests/transcript_pipeline/conftest.py | MODIFY | Keep only required fixture shape updates for meeting_minutes_artifact schema compatibility. |
| tests/transcript_pipeline/test_schemas_h01.py | MODIFY | Keep schema checks aligned with meeting_outcomes contract while preserving authority-safe vocabulary in touched regions. |
| tests/transcript_pipeline/test_h01b_hardening.py | MODIFY | Keep hardening checks aligned with outcome/source requirements and action completeness. |
| tests/transcript_pipeline/test_cpl04_scope_guard.py | CREATE | Add a guard test for allowed CPL-04 changed-file scope prefixes. |
| docs/review-actions/CPL-04_fix_actions.json | MODIFY | Record scope-fix follow-up and outcomes. |

## Contracts touched
- None (no new contract version publication in this scope-fix PR).

## Tests that must pass after execution
1. `python scripts/run_authority_shape_preflight.py --base-ref 23112c1aba722045ca29dc06c6ea1124a2e49c58 --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
2. `python scripts/run_authority_leak_guard.py --base-ref 23112c1aba722045ca29dc06c6ea1124a2e49c58 --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
3. `python scripts/run_system_registry_guard.py --base-ref 23112c1aba722045ca29dc06c6ea1124a2e49c58 --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json`
4. `pytest tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py`
5. `pytest tests/transcript_pipeline/test_schemas_h01.py tests/transcript_pipeline/test_h01b_hardening.py`
6. `pytest tests/transcript_pipeline`

## Scope exclusions
- Do not add allowlists.
- Do not edit governance/NS/lineage/observability surfaces.
- Do not weaken authority preflight scripts.
- Do not add non-transcript-pipeline module changes.
