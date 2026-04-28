# Canonical CI Gate Model (TST-02)

## Prompt type
BUILD

This model defines four canonical fail-closed gates plus a thin PR orchestrator.

## 1) Contract Gate
- **Purpose:** Validate contracts/schemas and preflight invariants.
- **Inputs:** changed refs, contract files, preflight policy.
- **Outputs:** `outputs/contract_gate/contract_gate_result.json`.
- **Artifact schema:** `contracts/schemas/contract_gate_result.schema.json`.
- **Fail-closed:** missing preflight artifact, non-zero preflight, invalid schema signal.
- **Mapped surfaces:** `scripts/run_contract_preflight.py`, `scripts/run_contract_impact_analysis.py`, contract tests.
- **Invariants protected:** schema authority, compatibility, fail-closed preflight.

## 2) Runtime Test Gate
- **Purpose:** Execute selected runtime tests with fallback smoke coverage.
- **Inputs:** changed paths, selection policy, baseline smoke inventory.
- **Outputs:** `outputs/test_selection_gate/test_selection_gate_result.json`, `outputs/runtime_test_gate/runtime_test_gate_result.json`.
- **Artifact schemas:** `test_selection_gate_result.schema.json`, `runtime_test_gate_result.schema.json`.
- **Fail-closed:** empty governed selection, invalid selected target, pytest failure.
- **Mapped surfaces:** PR pytest execution, pytest and Jest runtime suites.
- **Invariants protected:** required eval coverage, signal integrity, replay/lineage smoke checks.

## 3) Governance Signal Gate
- **Purpose:** Validate registry/governance/required-check consistency signals.
- **Inputs:** system registry, governance policy docs, required-check policy.
- **Outputs:** `outputs/governance_gate/governance_gate_result.json`.
- **Artifact schema:** `contracts/schemas/governance_gate_result.schema.json`.
- **Fail-closed:** missing governance evidence, required-check mismatch, registry guard mismatch.
- **Mapped surfaces:** `run_system_registry_guard.py`, `run_required_check_alignment_audit.py`, governance tests.

## 4) Readiness Evidence Gate
- **Purpose:** Collect and validate release-readiness evidence from upstream gate outputs.
- **Inputs:** upstream gate artifacts, replay/lineage evidence references, GOV-10 input references.
- **Outputs:** `outputs/readiness_evidence_gate/readiness_evidence_gate_result.json`.
- **Artifact schema:** `contracts/schemas/readiness_evidence_gate_result.schema.json`.
- **Fail-closed:** missing required upstream artifacts, missing required readiness inputs for deep mode.
- **Mapped surfaces:** replay/lineage test surfaces and GOV-10 input references.

## PR Gate Orchestrator
- **Purpose:** execute gates in canonical order and aggregate outcomes.
- **Output:** `outputs/pr_gate/pr_gate_result.json` (`contracts/schemas/pr_gate_result.schema.json`).
- **Constraint:** no policy shortcuts; only invokes gate scripts and aggregates statuses.

## Gate order
`Contract Gate -> Test Selection Gate -> Runtime Test Gate -> Governance Signal Gate -> Readiness Evidence Gate`.
