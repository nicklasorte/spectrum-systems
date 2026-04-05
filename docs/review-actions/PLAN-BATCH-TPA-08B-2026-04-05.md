# Plan — BATCH-TPA-08B Certification + Consumer Cohesion — 2026-04-05

## Prompt type
PLAN

## Roadmap item
BATCH-TPA-08B — Certification + Consumer Cohesion (R4, R2, R7, R6)

## Objective
Close the remaining TPA architecture review cohesion gaps by introducing a unified TPA certification envelope consumed by done/promotion gates, adding a contract-backed observability consumer, enforcing a schema-backed lightweight evidence omission allowlist, and governing complexity-budget recalibration cadence with explicit review evidence.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-TPA-08B-2026-04-05.md | CREATE | Required plan-first artifact for this multi-file contract/runtime/test hardening batch. |
| contracts/schemas/tpa_certification_envelope.schema.json | CREATE | Canonical governed envelope for unified TPA certification evidence and decisioning. |
| contracts/examples/tpa_certification_envelope.json | CREATE | Golden-path envelope example including cleanup-only compatible shape. |
| contracts/schemas/tpa_observability_consumer_record.schema.json | CREATE | Contract-backed downstream consumer surface for tpa_observability_summary. |
| contracts/examples/tpa_observability_consumer_record.json | CREATE | Golden example proving explicit consumer linkage. |
| contracts/schemas/complexity_budget_recalibration_record.schema.json | CREATE | Governed cadence/trigger/review artifact for complexity-budget recalibration. |
| contracts/examples/complexity_budget_recalibration_record.json | CREATE | Golden example for cadence + trigger + governance hook evidence. |
| contracts/schemas/tpa_policy_composition.schema.json | MODIFY | Add schema-backed lightweight evidence omission allowlist rules. |
| config/policy/tpa_policy_composition.json | MODIFY | Provide governed lightweight evidence omission allowlist values consumed by runtime. |
| spectrum_systems/modules/governance/tpa_policy_composition.py | MODIFY | Enforce contract-backed lightweight evidence allowlist resolution. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Emit tpa_certification_envelope, emit observability consumer artifact, and enforce lightweight omission allowlist deterministically. |
| spectrum_systems/modules/governance/done_certification.py | MODIFY | Consume and validate tpa_certification_envelope for TPA required scope fail-closed certification. |
| spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py | MODIFY | Promotion certification gate consumes tpa_certification_envelope and blocks when envelope requirements fail. |
| spectrum_systems/modules/runtime/tpa_complexity_governance.py | MODIFY | Add complexity recalibration artifact builder and observability-consumer builder helpers. |
| tests/test_tpa_sequence_runner.py | MODIFY | Coverage for envelope generation, cleanup-only envelope path, lightweight allowlist enforcement, and deterministic outputs. |
| tests/test_done_certification.py | MODIFY | Coverage for done gate envelope consumption and fail-closed missing-envelope behavior. |
| tests/test_evaluation_enforcement_bridge.py | MODIFY | Coverage for promotion gate envelope consumption and fail-closed missing/invalid envelope behavior. |
| tests/test_tpa_complexity_governance.py | MODIFY | Coverage for observability consumer contract and complexity recalibration cadence artifact builder determinism. |
| tests/test_tpa_policy_composition.py | MODIFY | Coverage for lightweight evidence omission allowlist contract and resolution behavior. |
| tests/test_contracts.py | MODIFY | Validate new/updated contract examples. |
| contracts/standards-manifest.json | MODIFY | Register new contracts and version bumps for updated contracts. |

## Contracts touched
- `tpa_certification_envelope` (new)
- `tpa_observability_consumer_record` (new)
- `complexity_budget_recalibration_record` (new)
- `tpa_policy_composition` (version bump)
- `done_certification_record` (version bump if envelope reference surface changes)

## Tests that must pass after execution
1. `pytest tests/test_tpa_sequence_runner.py tests/test_done_certification.py tests/test_evaluation_enforcement_bridge.py tests/test_tpa_complexity_governance.py tests/test_tpa_policy_composition.py tests/test_contracts.py`
2. `pytest tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign TPA plan/build/simplify/gate semantics beyond envelope cohesion and lightweight omission guardrails.
- Do not add automatic policy mutation or automatic budget recalibration execution.
- Do not introduce new artifact classes outside existing repo taxonomy.

## Dependencies
- BATCH-TPA-08A outputs from `docs/review-actions/PLAN-BATCH-TPA-08A-2026-04-05.md`.
- Existing TPA governance/runtime seams from BATCH-TPA-02/03/04/06.
