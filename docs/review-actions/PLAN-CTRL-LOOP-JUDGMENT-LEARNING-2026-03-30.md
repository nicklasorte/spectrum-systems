# Plan — CTRL-LOOP-01 Judgment Learning Bundle — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-01 (grouped PQX judgment-learning extension)

## Objective
Extend the merged judgment-eval foundation with deterministic replay-reference comparison, governed outcome labels, longitudinal calibration artifacts, and judgment drift-signal artifacts with fail-closed integration tests.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CTRL-LOOP-JUDGMENT-LEARNING-2026-03-30.md | CREATE | Required plan-first execution record for grouped multi-file slice |
| spectrum_systems/modules/runtime/judgment_eval_runner.py | MODIFY | Extend replay consistency behavior and emit richer deterministic replay comparison details |
| spectrum_systems/modules/runtime/judgment_engine.py | MODIFY | Thread optional replay reference artifact into judgment eval execution |
| spectrum_systems/modules/runtime/judgment_learning.py | CREATE | Add deterministic label ingestion, calibration runner, and drift-signal computation seams |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Enforce replay reference requirement when policy requires it and pass replay reference artifact |
| contracts/schemas/judgment_eval_result.schema.json | MODIFY | Govern extended replay comparison details and non-scaffold calibration/drift metadata |
| contracts/examples/judgment_eval_result.json | MODIFY | Keep example aligned with schema changes |
| contracts/schemas/judgment_policy.schema.json | MODIFY | Add replay reference requirement toggle in judgment eval requirements |
| contracts/examples/judgment_policy.json | MODIFY | Demonstrate replay reference requirement behavior |
| contracts/schemas/judgment_outcome_label.schema.json | CREATE | Contract for governed ingestion of labeled judgment outcomes |
| contracts/examples/judgment_outcome_label.json | CREATE | Golden-path example for outcome label artifact |
| contracts/schemas/judgment_calibration_result.schema.json | CREATE | Contract for deterministic longitudinal calibration artifact |
| contracts/examples/judgment_calibration_result.json | CREATE | Golden-path example for calibration artifact |
| contracts/schemas/judgment_drift_signal.schema.json | CREATE | Contract for deterministic judgment drift signal artifact |
| contracts/examples/judgment_drift_signal.json | CREATE | Golden-path example for drift signal artifact |
| contracts/standards-manifest.json | MODIFY | Publish new contracts and schema version updates |
| tests/test_judgment_learning.py | CREATE | Integration coverage for replay mismatch, label ingestion, calibration determinism, drift determinism, and fail-closed behaviors |
| tests/test_cycle_runner.py | MODIFY | Add coverage for required replay-reference path blocking when policy requires reference artifact |
| tests/test_contracts.py | MODIFY | Validate new contract examples |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document replay reference sourcing, label ingestion, calibration, drift behavior, and control-loop feed-forward intent |
| docs/roadmap/system_roadmap.md | MODIFY | Register grouped PQX judgment-learning slice status in operational roadmap mirror |

## Contracts touched
- judgment_eval_result (schema + example update)
- judgment_policy (schema + example update)
- judgment_outcome_label (new)
- judgment_calibration_result (new)
- judgment_drift_signal (new)
- standards-manifest version bump and contract registry updates

## Tests that must pass after execution
1. `pytest tests/test_judgment_learning.py tests/test_cycle_runner.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign cycle state machine architecture.
- Do not add a new control plane or orchestration path.
- Do not add probabilistic/statistical drift frameworks beyond deterministic threshold deltas.
- Do not change unrelated roadmap rows or unrelated contracts.

## Dependencies
- CTRL-LOOP-01 judgment + precedent + eval foundation must already be merged.
