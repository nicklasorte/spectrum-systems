# TAX/BAX/CAX Phase 1 — Registry and Contracts

## Registry updates
- Added TAX, BAX, and CAX authority definitions to `docs/architecture/system_registry.md`.
- Added TAX, BAX, and CAX entries and interaction edges to `contracts/examples/system_registry_artifact.json`.

## Contract foundation
Added strict Draft 2020-12 schemas + examples for:
- TAX: `termination_policy`, `termination_signal_record`, `termination_decision`, `termination_audit_record`
- BAX: `system_budget_policy`, `system_budget_status_v2`, `budget_consumption_record`, `budget_control_decision`
- CAX: `control_arbitration_policy`, `control_arbitration_record`, `control_arbitration_reason_bundle`, `cde_arbitration_input_bundle`

## Standards manifest
- Bumped manifest version to `1.3.124`.
- Registered all 12 new artifact contracts with schema and example paths.

## Repo-native deviations
- Reused existing `coordination` artifact class to avoid introducing a parallel class taxonomy.
- Maintained CDE final closure ownership; CAX emits only preparation artifacts.
