# Plan — BATCH-FRE-001 — 2026-04-12

## Prompt type
BUILD

## Roadmap item
FRE-001 (FRE-01 through FRE-15)

## Objective
Implement end-to-end FRE governed repair artifacts, policy gating, replay/provenance checks, review/override records, metrics signals, judgment slice, policy candidate compilation, and promotion hard-gate enforcement with deterministic tests.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-FRE-001-2026-04-12.md | CREATE | Required plan-first artifact for >2-file BUILD execution |
| spectrum_systems/modules/runtime/fre_repair_flow.py | MODIFY | Implement FRE-01..FRE-15 runtime logic |
| tests/test_fre_repair_flow.py | MODIFY | Extend deterministic tests to cover FRE-01..FRE-15 behaviors |
| tests/test_contract_enforcement.py | MODIFY | Assert standards-manifest registration for new FRE contract surfaces |
| contracts/standards-manifest.json | MODIFY | Register and version FRE contract artifacts |
| contracts/schemas/repair_candidate.schema.json | MODIFY | Add provenance/replay requirements |
| contracts/schemas/repair_eval_result.schema.json | MODIFY | Tighten eval requirements |
| contracts/schemas/repair_readiness_candidate.schema.json | MODIFY | Tighten non-authority/readiness requirements |
| contracts/schemas/repair_effectiveness_record.schema.json | MODIFY | Add linkage to originating failure and observed outcome |
| contracts/schemas/repair_recurrence_record.schema.json | MODIFY | Add recurrence clustering and hotspot fields |
| contracts/schemas/repair_bundle.schema.json | MODIFY | Add replay/provenance binding fields |
| contracts/schemas/repair_template_candidate.schema.json | CREATE | FRE-08 governed template admission artifact |
| contracts/schemas/repair_scope_policy_gate.schema.json | CREATE | FRE-09 policy gate artifact |
| contracts/schemas/repair_review_record.schema.json | CREATE | FRE-11 review artifact |
| contracts/schemas/repair_override_record.schema.json | CREATE | FRE-11 override artifact |
| contracts/schemas/repair_budget_signal.schema.json | CREATE | FRE-12 operational signal artifact |
| contracts/schemas/repair_judgment_slice.schema.json | CREATE | FRE-13 judgment slice artifact |
| contracts/schemas/repair_policy_candidate.schema.json | CREATE | FRE-14 policy candidate compilation artifact |
| contracts/schemas/fre_promotion_gate_record.schema.json | CREATE | FRE-15 promotion hard gate artifact |
| contracts/examples/repair_candidate.json | MODIFY | Keep example aligned to tightened contract |
| contracts/examples/repair_eval_result.json | MODIFY | Keep example aligned to tightened contract |
| contracts/examples/repair_readiness_candidate.json | MODIFY | Keep example aligned to tightened contract |
| contracts/examples/repair_effectiveness_record.json | MODIFY | Keep example aligned to tightened contract |
| contracts/examples/repair_recurrence_record.json | MODIFY | Keep example aligned to tightened contract |
| contracts/examples/repair_bundle.json | MODIFY | Keep example aligned to tightened contract |
| contracts/examples/repair_template_candidate.json | CREATE | Example for FRE-08 |
| contracts/examples/repair_scope_policy_gate.json | CREATE | Example for FRE-09 |
| contracts/examples/repair_review_record.json | CREATE | Example for FRE-11 review |
| contracts/examples/repair_override_record.json | CREATE | Example for FRE-11 override |
| contracts/examples/repair_budget_signal.json | CREATE | Example for FRE-12 |
| contracts/examples/repair_judgment_slice.json | CREATE | Example for FRE-13 |
| contracts/examples/repair_policy_candidate.json | CREATE | Example for FRE-14 |
| contracts/examples/fre_promotion_gate_record.json | CREATE | Example for FRE-15 |

## Contracts touched
repair_candidate, repair_eval_result, repair_readiness_candidate, repair_effectiveness_record, repair_recurrence_record, repair_bundle, repair_template_candidate, repair_scope_policy_gate, repair_review_record, repair_override_record, repair_budget_signal, repair_judgment_slice, repair_policy_candidate, fre_promotion_gate_record.

## Tests that must pass after execution
1. `pytest tests/test_fre_repair_flow.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not change non-FRE runtime modules.
- Do not alter control or enforcement authority ownership.
- Do not introduce network-dependent behavior.

## Dependencies
- Existing FRE repair foundation and RAX operational gate support remain baseline prerequisites.
