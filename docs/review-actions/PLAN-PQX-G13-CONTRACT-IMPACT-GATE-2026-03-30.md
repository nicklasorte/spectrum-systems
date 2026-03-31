# Plan — PQX-G13 Contract Impact Gate — 2026-03-30

## Prompt type
PLAN

## Roadmap item
G13 — Governed contract-impact gate before PQX execution

## Objective
Add a deterministic, fail-closed contract-impact analyzer and schema-bound artifact, then wire PQX pre-execution gating to block breaking/indeterminate contract impact.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-G13-CONTRACT-IMPACT-GATE-2026-03-30.md | CREATE | Required plan artifact for multi-file governed change |
| contracts/schemas/contract_impact_artifact.schema.json | CREATE | New governed schema for contract-impact output |
| contracts/examples/contract_impact_artifact.json | CREATE | Golden-path example for new contract-impact artifact |
| contracts/examples/contract_impact_artifact.example.json | CREATE | Golden-path fixture required by repo validation discipline |
| contracts/standards-manifest.json | MODIFY | Register new governed contract in canonical manifest |
| spectrum_systems/governance/__init__.py | CREATE | Governance package export for contract-impact analyzer |
| spectrum_systems/governance/contract_impact.py | CREATE | Deterministic contract-impact analysis engine |
| scripts/run_contract_impact_analysis.py | CREATE | Thin CLI for analysis + artifact validation + exit gating |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Pre-execution hard gate consuming or generating contract-impact artifact |
| scripts/pqx_runner.py | MODIFY | CLI wiring to pass contract-impact inputs into PQX runner |
| tests/test_contract_impact_analysis.py | CREATE | Analyzer + artifact + fail-closed detection tests |
| tests/test_pqx_slice_runner.py | MODIFY | PQX gate allow/block behavior tests for contract-impact artifacts |
| tests/test_contracts.py | MODIFY | Ensure new contract example validates in core contract suite |
| docs/governance/contract-impact-gate.md | CREATE | Minimal operating guidance for governed contract-impact gate |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document PQX pre-execution contract-impact gating seam |

## Contracts touched
- Add `contracts/schemas/contract_impact_artifact.schema.json`.
- Add `contracts/examples/contract_impact_artifact.json`.
- Update `contracts/standards-manifest.json` with `contract_impact_artifact` entry and version metadata.

## Tests that must pass after execution
1. `pytest tests/test_contract_impact_analysis.py`
2. `pytest tests/test_pqx_slice_runner.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not introduce external dependency graph services or multi-repo crawlers.
- Do not redesign PQX execution architecture.
- Do not refactor unrelated contracts or runtime modules.

## Dependencies
- Existing contract loader + schema validation seams in `spectrum_systems/contracts/__init__.py`.
- Existing PQX entrypoint seam in `spectrum_systems/modules/runtime/pqx_slice_runner.py`.
