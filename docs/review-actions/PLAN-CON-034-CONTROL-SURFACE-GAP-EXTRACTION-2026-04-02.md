# Plan — CON-034 Control Surface Gap Extraction — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-034 — Control Surface Gap Extraction

## Objective
Create a deterministic, schema-governed `control_surface_gap_packet` artifact and extraction module that converts manifest/enforcement/obedience/trust-spine/certification inputs into bounded machine-readable gap signals.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-034-CONTROL-SURFACE-GAP-EXTRACTION-2026-04-02.md | CREATE | Required plan-first artifact for CON-034 scope declaration. |
| PLANS.md | MODIFY | Register the CON-034 plan in active plans table. |
| contracts/schemas/control_surface_gap_packet.schema.json | CREATE | Define governed schema for deterministic control-surface gap packet output. |
| contracts/examples/control_surface_gap_packet.json | CREATE | Provide canonical golden-path packet example for validation and downstream consumption. |
| spectrum_systems/modules/runtime/control_surface_gap_extractor.py | MODIFY | Add deterministic extraction logic for `control_surface_gap_packet` with strict fail-closed validation. |
| scripts/build_control_surface_gap_packet.py | CREATE | Add thin CLI wrapper that loads explicit inputs, validates, extracts packet, validates output, writes artifact, and exits fail-closed on BLOCK/malformed input. |
| tests/test_control_surface_gap_extractor.py | MODIFY | Add focused CON-034 tests for extractor decision logic, deterministic identity, malformed handling, and CLI behavior. |
| tests/test_contracts.py | MODIFY | Validate new `control_surface_gap_packet` example against its schema. |
| contracts/standards-manifest.json | MODIFY | Register `control_surface_gap_packet` contract pin metadata. |

## Contracts touched
- `contracts/schemas/control_surface_gap_packet.schema.json` (new)
- `contracts/standards-manifest.json` (add `control_surface_gap_packet` entry + manifest version metadata update)

## Tests that must pass after execution
1. `pytest -q tests/test_control_surface_gap_extractor.py`
2. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/build_control_surface_gap_packet.py --manifest contracts/examples/control_surface_manifest.json --enforcement contracts/examples/control_surface_enforcement_result.json --obedience contracts/examples/control_surface_obedience_result.json --trust-spine contracts/examples/trust_spine_evidence_cohesion_result.json --done-certification contracts/examples/done_certification_record.json --output outputs/control_surface_gap_packet/control_surface_gap_packet.json --generated-at 2026-04-02T00:00:00Z --trace-id trace-con-034-example`
5. `python scripts/run_contract_preflight.py --changed-path spectrum_systems/modules/runtime/control_surface_gap_extractor.py --changed-path scripts/build_control_surface_gap_packet.py --changed-path contracts/schemas/control_surface_gap_packet.schema.json --changed-path contracts/examples/control_surface_gap_packet.json --changed-path tests/test_control_surface_gap_extractor.py --changed-path contracts/standards-manifest.json`
6. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not implement PQX task creation or fix-plan generation.
- Do not redesign existing preflight/roadmap machinery.
- Do not add heuristic or probabilistic remediation logic.
- Do not broaden control-surface discovery beyond explicit provided inputs.

## Dependencies
- CON-029 control-surface manifest contract/module present.
- CON-030 control-surface enforcement result contract/module present.
- CON-031 control-surface obedience result contract/module present.
- CON-033 trust-spine evidence cohesion seam present.
