# Plan — CON-031 Manifest-to-Runtime Obedience Proof — 2026-04-01

## Prompt type
PLAN

## Roadmap item
CON-031 — Manifest-to-Runtime Obedience Proof

## Objective
Add a narrow deterministic obedience-proof artifact and evaluator that proves selected governed control surfaces are actively obeyed by live certification/promotion seams, with fail-closed blocking on contradiction or missing evidence.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-031-MANIFEST-RUNTIME-OBEDIENCE-PROOF-2026-04-01.md | CREATE | Required PLAN artifact for CON-031 multi-file contract/module/seam implementation. |
| PLANS.md | MODIFY | Register active CON-031 plan in plan index. |
| contracts/schemas/control_surface_obedience_result.schema.json | CREATE | Publish governed machine-readable obedience-proof contract. |
| contracts/examples/control_surface_obedience_result.json | CREATE | Golden-path example for obedience-proof result contract. |
| contracts/standards-manifest.json | MODIFY | Pin the new obedience-result contract version in canonical standards registry. |
| spectrum_systems/modules/runtime/control_surface_obedience.py | CREATE | Implement pure deterministic fail-closed obedience evaluator over selected governed surfaces. |
| scripts/run_control_surface_obedience.py | CREATE | Thin CLI wrapper with contract validation, deterministic artifact write, and non-zero block semantics. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Wire obedience result consumption into live promotion decision path with fail-closed BLOCK behavior. |
| tests/test_control_surface_obedience.py | CREATE | Focused deterministic regression coverage for obedience evaluator and CLI semantics. |
| tests/test_sequence_transition_policy.py | MODIFY | Cover promotion seam obedience-result consumption and contradiction blocking. |
| tests/test_contracts.py | MODIFY | Validate new obedience-result example against schema. |

## Contracts touched
- `contracts/schemas/control_surface_obedience_result.schema.json` (new, v1.0.0)
- `contracts/standards-manifest.json` (add `control_surface_obedience_result` pin)

## Tests that must pass after execution
1. `pytest -q tests/test_control_surface_obedience.py tests/test_done_certification.py tests/test_sequence_transition_policy.py`
2. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py tests/test_control_surface_manifest.py tests/test_control_surface_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/build_control_surface_manifest.py --output-dir outputs/control_surface_manifest`
5. `python scripts/run_control_surface_enforcement.py --manifest outputs/control_surface_manifest/control_surface_manifest.json --output-dir outputs/control_surface_enforcement`
6. `python scripts/run_control_surface_obedience.py --manifest outputs/control_surface_manifest/control_surface_manifest.json --enforcement-result outputs/control_surface_enforcement/control_surface_enforcement_result.json --output-dir outputs/control_surface_obedience`
7. `python scripts/run_contract_preflight.py --changed-path spectrum_systems/modules/runtime/control_surface_obedience.py --changed-path scripts/run_control_surface_obedience.py --changed-path contracts/schemas/control_surface_obedience_result.schema.json --changed-path contracts/examples/control_surface_obedience_result.json --changed-path tests/test_control_surface_obedience.py --changed-path contracts/standards-manifest.json`
8. `PLAN_FILES='PLANS.md docs/review-actions/PLAN-CON-031-MANIFEST-RUNTIME-OBEDIENCE-PROOF-2026-04-01.md contracts/schemas/control_surface_obedience_result.schema.json contracts/examples/control_surface_obedience_result.json contracts/standards-manifest.json spectrum_systems/modules/runtime/control_surface_obedience.py scripts/run_control_surface_obedience.py spectrum_systems/orchestration/sequence_transition_policy.py tests/test_control_surface_obedience.py tests/test_sequence_transition_policy.py tests/test_contracts.py' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign trust-spine invariant policy logic.
- Do not broaden control surface inventory beyond narrow governed subset.
- Do not add heuristic scanning or filename-inferred evidence.
- Do not add broad new orchestration layers.
- Do not modify done-certification decision model beyond existing behavior.

## Dependencies
- CON-029 control surface manifest baseline must exist.
- CON-030 control surface enforcement contract/module wiring must exist.
