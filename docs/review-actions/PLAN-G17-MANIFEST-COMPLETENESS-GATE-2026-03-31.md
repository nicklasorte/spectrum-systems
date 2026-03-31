# Plan — G17 Manifest Completeness Gate — 2026-03-31

## Prompt type
PLAN

## Roadmap item
G17 — Manifest Completeness Gate (Pre-PR Structural Integrity)

## Objective
Add a strict, fail-closed manifest completeness validator and wire it into CLI and PQX pre-execution gating so incomplete standards manifest contract entries block execution.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-G17-MANIFEST-COMPLETENESS-GATE-2026-03-31.md | CREATE | Required multi-file execution plan for G17 scope. |
| PLANS.md | MODIFY | Register active G17 plan in active plans table. |
| spectrum_systems/governance/manifest_validator.py | CREATE | Implement strict standards-manifest completeness validation logic. |
| spectrum_systems/governance/__init__.py | MODIFY | Export validator entrypoint for runtime/CLI usage. |
| scripts/validate_manifest.py | CREATE | Add deterministic CLI gate for manifest completeness checks. |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Enforce manifest completeness prior to slice execution (fail-closed). |
| tests/test_manifest_completeness.py | CREATE | Add deterministic unit tests for missing/null/enum/valid paths. |
| tests/test_pqx_slice_runner.py | MODIFY | Cover PQX manifest gate block path and valid path behavior. |
| docs/governance/manifest-completeness-gate.md | CREATE | Document gate purpose, required fields, failure examples, and CI risk prevention. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_manifest_completeness.py`
2. `pytest tests/test_pqx_slice_runner.py`
3. `python scripts/validate_manifest.py`

## Scope exclusions
- Do not modify `contracts/standards-manifest.json` contents in this slice.
- Do not alter unrelated PQX orchestration or policy logic beyond manifest gate insertion.
- Do not add third-party dependencies.

## Dependencies
- docs/roadmaps/system_roadmap.md remains authoritative for roadmap context.
