# Plan — ARTIFACT ENVELOPE HARDENING — 2026-03-24

## Prompt type
PLAN

## Roadmap item
SF-14.6 follow-on hardening — canonical governed artifact envelope enforcement

## Objective
Establish a single canonical governed artifact envelope contract and enforce it across release/eval/runtime-chaos artifacts without changing control, release, or error-budget policy behavior.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-ARTIFACT-ENVELOPE-HARDENING-2026-03-24.md | CREATE | Required PLAN artifact before multi-file BUILD work. |
| PLANS.md | MODIFY | Register active plan entry. |
| contracts/schemas/artifact_envelope.schema.json | MODIFY | Define canonical governed envelope fields and trace refs semantics. |
| contracts/schemas/evaluation_release_record.schema.json | MODIFY | Align targeted governed artifact to canonical envelope semantics. |
| contracts/schemas/evaluation_ci_gate_result.schema.json | MODIFY | Align targeted governed artifact to canonical envelope semantics. |
| contracts/schemas/eval_coverage_summary.schema.json | MODIFY | Align targeted governed artifact to canonical envelope semantics. |
| contracts/schemas/evaluation_control_chaos_summary.schema.json | CREATE | Add contract for runtime chaos summary output and align envelope semantics. |
| contracts/examples/artifact_envelope.json | CREATE | Add canonical envelope example path requested by slice. |
| contracts/examples/artifact_envelope.example.json | MODIFY | Keep fallback example aligned to canonical envelope semantics. |
| contracts/examples/evaluation_release_record.json | MODIFY | Ensure example matches updated envelope structure. |
| contracts/examples/evaluation_ci_gate_result.json | MODIFY | Ensure example matches updated envelope structure. |
| contracts/examples/eval_coverage_summary.json | MODIFY | Ensure example matches updated envelope structure. |
| contracts/examples/evaluation_control_chaos_summary.json | CREATE | Golden-path example for runtime chaos summary contract. |
| contracts/standards-manifest.json | MODIFY | Register/advance canonical envelope and impacted contract versions. |
| spectrum_systems/utils/artifact_envelope.py | CREATE | Shared repo-native helper for envelope build/trace_refs validation. |
| spectrum_systems/utils/__init__.py | MODIFY | Export envelope helper functions. |
| spectrum_systems/modules/evaluation/eval_coverage_reporting.py | MODIFY | Build canonical envelope via shared helper. |
| spectrum_systems/modules/runtime/release_canary.py | MODIFY | Build canonical envelope via shared helper. |
| spectrum_systems/modules/runtime/control_loop_chaos.py | MODIFY | Build canonical envelope via shared helper and validate artifact schema. |
| scripts/run_eval_ci_gate.py | MODIFY | Build canonical envelope via shared helper for gate artifact emission. |
| tests/test_artifact_envelope.py | MODIFY | Validate new canonical envelope contract + example path. |
| tests/test_artifact_envelope_helpers.py | CREATE | Add helper-level positive/negative tests for trace_refs/envelope construction. |
| tests/test_release_canary.py | MODIFY | Update assertions for canonical trace_refs shape and schema version bumps. |
| tests/test_control_loop_chaos.py | MODIFY | Validate chaos summary envelope semantics and schema conformance. |
| tests/test_contracts.py | MODIFY | Ensure new/updated governed examples validate. |

## Contracts touched
- artifact_envelope (modify + version bump)
- eval_coverage_summary (modify + version bump)
- evaluation_ci_gate_result (modify + version bump)
- evaluation_release_record (modify + version bump)
- evaluation_control_chaos_summary (new contract registration)
- standards_manifest (version and contract pins update)

## Tests that must pass after execution
1. `pytest tests/test_artifact_envelope.py tests/test_artifact_envelope_helpers.py`
2. `pytest tests/test_release_canary.py tests/test_control_loop_chaos.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify queue/orchestration modules.
- Do not modify control thresholds, release decision precedence, or error-budget policy logic.
- Do not refactor unrelated artifact schemas.
- Do not introduce new third-party dependencies.

## Dependencies
- Existing SF-07 / SF-12 / SF-14 / SF-14.6 slices present in mainline must remain behaviorally stable.
