# Plan — CON-029 CONTROL SURFACE MANIFEST — 2026-04-01

## Prompt type
PLAN

## Roadmap item
CON-029 — CONTROL-SURFACE MANIFEST + INVARIANT COVERAGE REGISTRY

## Objective
Add a strict governed control-surface manifest contract and deterministic builder that inventories active trust/control surfaces, invariant attachment, test coverage, and machine-readable coverage gaps.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-029-CONTROL-SURFACE-MANIFEST-2026-04-01.md | CREATE | Plan-first artifact required before multi-file contract/module changes. |
| PLANS.md | MODIFY | Register CON-029 plan in active plans table. |
| contracts/schemas/control_surface_manifest.schema.json | CREATE | Canonical strict schema for governed manifest artifact. |
| contracts/examples/control_surface_manifest.json | CREATE | Golden-path deterministic contract example. |
| contracts/standards-manifest.json | MODIFY | Publish contract in authoritative standards registry and bump standards version metadata. |
| spectrum_systems/modules/runtime/control_surface_manifest.py | CREATE | Pure deterministic manifest builder with fail-closed checks and explicit governed surface mapping. |
| scripts/build_control_surface_manifest.py | CREATE | Thin CLI to build, validate, and write manifest artifact. |
| tests/test_control_surface_manifest.py | CREATE | Deterministic module and CLI tests for manifest correctness/fail-closed behavior. |

## Contracts touched
- New: `control_surface_manifest` (`contracts/schemas/control_surface_manifest.schema.json`)
- New example: `contracts/examples/control_surface_manifest.json`
- Update registry: `contracts/standards-manifest.json`

## Tests that must pass after execution
1. `pytest -q tests/test_control_surface_manifest.py`
2. `pytest -q tests/test_sequence_transition_policy.py tests/test_done_certification.py tests/test_evaluation_control.py tests/test_contracts.py`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/build_control_surface_manifest.py --output-dir outputs/control_surface_manifest`
5. `python scripts/run_contract_preflight.py --changed-path spectrum_systems/modules/runtime/control_surface_manifest.py --changed-path scripts/build_control_surface_manifest.py --changed-path contracts/schemas/control_surface_manifest.schema.json --changed-path contracts/examples/control_surface_manifest.json --changed-path tests/test_control_surface_manifest.py --changed-path contracts/standards-manifest.json`
6. `PLAN_FILES="PLANS.md docs/review-actions/PLAN-CON-029-CONTROL-SURFACE-MANIFEST-2026-04-01.md scripts/build_control_surface_manifest.py spectrum_systems/modules/runtime/control_surface_manifest.py contracts/schemas/control_surface_manifest.schema.json contracts/examples/control_surface_manifest.json tests/test_control_surface_manifest.py contracts/standards-manifest.json" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change runtime decision policy semantics in evaluation/replay/promotion/certification modules.
- Do not add dynamic reflection/discovery crawlers for surface detection.
- Do not modify existing schema contracts unrelated to `control_surface_manifest`.
- Do not refactor existing control modules beyond imports needed for this narrow slice.

## Dependencies
- CON-024 through CON-028 trust-spine and fail-closed seams must remain authoritative and unchanged.
