# Plan — CTRL-LOOP-01 Judgment Eval Bundle — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-01 grouped PQX slice — judgment eval runner + fail-closed gating

## Objective
Extend the existing autonomous cycle judgment foundation with deterministic judgment evaluation artifacts (evidence coverage, policy alignment, replay consistency), fail-closed control gating, and integration tests proving blocking/progression behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/judgment_engine.py | MODIFY | Reuse judgment seam and emit structured claim/eval-ready fields; invoke eval runner. |
| spectrum_systems/modules/runtime/judgment_eval_runner.py | CREATE | Repo-native deterministic judgment eval runner implementation. |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Integrate fail-closed required judgment-eval gating in control transition. |
| contracts/schemas/judgment_eval_result.schema.json | MODIFY | Harden schema for multi-eval judgment_eval_result with deterministic machine-readable checks/scores. |
| contracts/schemas/judgment_record.schema.json | MODIFY | Add structured claim support with evidence linkage for deterministic evidence coverage evaluation. |
| contracts/schemas/judgment_policy.schema.json | MODIFY | Add optional explicit judgment eval policy requirements thresholds/toggles. |
| contracts/schemas/cycle_manifest.schema.json | MODIFY | Add optional judgment eval control config fields for required eval types and replay reference. |
| contracts/examples/judgment_eval_result.json | MODIFY | Update golden example to new judgment eval result shape. |
| contracts/examples/judgment_record.json | MODIFY | Update golden example with claims_considered evidence linkage fields. |
| contracts/examples/judgment_policy.json | MODIFY | Add eval requirements config example. |
| contracts/examples/cycle_manifest.json | MODIFY | Add judgment eval gating configuration example fields. |
| contracts/standards-manifest.json | MODIFY | Version bump and contract entry updates for changed schemas/examples. |
| tests/test_cycle_runner.py | MODIFY | Add integration tests for judgment-eval-driven blocking and progression. |
| tests/test_contracts.py | MODIFY | Ensure updated examples/schemas remain validated through existing contract surface if needed. |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document judgment eval flow, control gating behavior, calibration/drift scaffolding seams. |
| docs/roadmap/system_roadmap.md | MODIFY | Record completion status for this grouped judgment eval slice. |
| docs/reviews/autonomous-loop-judgment-eval-slice-status-2026-03-30.md | CREATE | Repo-native status/review artifact for this slice completion summary. |

## Contracts touched
- `contracts/schemas/judgment_eval_result.schema.json`
- `contracts/schemas/judgment_record.schema.json`
- `contracts/schemas/judgment_policy.schema.json`
- `contracts/schemas/cycle_manifest.schema.json`
- `contracts/standards-manifest.json` (version bump)

## Tests that must pass after execution
1. `pytest tests/test_cycle_runner.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign cycle state machine or introduce a parallel control plane.
- Do not refactor unrelated runtime/evaluation modules.
- Do not implement full analytics platform for calibration/drift; add thin scaffold only.
- Do not modify deprecated roadmap execution files.

## Dependencies
- Prior CTRL-LOOP-01 judgment foundation slice must be merged (judgment policy/record/application + initial cycle integration).
- Existing cycle manifest and runner seams remain the authoritative orchestration surface.
