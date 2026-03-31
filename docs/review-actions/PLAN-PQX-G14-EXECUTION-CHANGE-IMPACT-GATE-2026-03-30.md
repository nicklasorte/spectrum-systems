# Plan — PQX G14 Execution Change Impact Gate — 2026-03-30

## Prompt type
PLAN

## Roadmap item
G14 — Pre-execution execution-path change impact gate (contract-complement seam)

## Objective
Implement a deterministic fail-closed execution change impact analyzer + contract + PQX gate wiring so risky runtime/governance/control-path file changes block execution without explicit evidence.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/execution_change_impact_artifact.schema.json | CREATE | Add strict governed artifact contract for execution-impact gate output |
| contracts/examples/execution_change_impact_artifact.json | CREATE | Add canonical example payload |
| contracts/examples/execution_change_impact_artifact.example.json | CREATE | Add alternate example payload for docs/tests parity |
| contracts/standards-manifest.json | MODIFY | Register contract version pin |
| spectrum_systems/governance/execution_change_impact.py | CREATE | Deterministic path-impact analyzer implementation |
| spectrum_systems/governance/__init__.py | MODIFY | Export analyzer APIs |
| scripts/run_execution_change_impact_analysis.py | CREATE | Thin CLI wrapper for deterministic analysis + schema validation |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Enforce execution-impact gate alongside contract-impact gate |
| scripts/pqx_runner.py | MODIFY | Surface execution-impact inputs/artifact options |
| docs/governance/execution-change-impact-gate.md | CREATE | Governance doc for G14 gate semantics |
| docs/governance/contract-impact-gate.md | MODIFY | Clarify dual-gate role boundaries |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document pre-execution dual-gate requirement in loop model |
| PLANS.md | MODIFY | Register this plan in active plans table |
| docs/review-actions/PLAN-PQX-G14-EXECUTION-CHANGE-IMPACT-GATE-2026-03-30.md | CREATE | PLAN artifact for this BUILD slice |
| tests/test_execution_change_impact_analysis.py | CREATE | Focused deterministic analyzer and fail-closed coverage |
| tests/test_pqx_slice_runner.py | MODIFY | Validate PQX blocking/allow behavior for execution-impact gate |
| tests/test_contracts.py | MODIFY | Validate new contract examples |

## Contracts touched
- Added: `execution_change_impact_artifact` (schema version `1.0.0`).
- Updated: `contracts/standards-manifest.json` to pin the new contract.

## Tests that must pass after execution
1. `pytest tests/test_execution_change_impact_analysis.py`
2. `pytest tests/test_pqx_slice_runner.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `PLAN_FILES="contracts/schemas/execution_change_impact_artifact.schema.json contracts/examples/execution_change_impact_artifact.json contracts/examples/execution_change_impact_artifact.example.json contracts/standards-manifest.json spectrum_systems/governance/execution_change_impact.py spectrum_systems/governance/__init__.py scripts/run_execution_change_impact_analysis.py spectrum_systems/modules/runtime/pqx_slice_runner.py scripts/pqx_runner.py docs/governance/execution-change-impact-gate.md docs/governance/contract-impact-gate.md docs/architecture/autonomous_execution_loop.md PLANS.md docs/review-actions/PLAN-PQX-G14-EXECUTION-CHANGE-IMPACT-GATE-2026-03-30.md tests/test_execution_change_impact_analysis.py tests/test_pqx_slice_runner.py tests/test_contracts.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign multi-step PQX autonomy or execution topology.
- Do not replace or weaken contract-impact gate behavior.
- Do not add LLM/non-deterministic classification logic.
- Do not modify unrelated roadmap rows, queue orchestration flows, or downstream repos.

## Dependencies
- Existing PQX single-step fail-closed execution path and contract-impact gate remain authoritative.
- Existing contract loader/validator seam in `spectrum_systems/contracts` remains authoritative.
