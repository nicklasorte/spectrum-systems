# Canonical CI Gate Model (TST-02)

## Prompt type
BUILD

This model defines four canonical fail-closed gates plus a thin PR orchestrator.

## 1) Contract Gate
- **Purpose:** Validate contracts/schemas and contract-preflight invariants.
- **Inputs:** changed refs, contract files, preflight policy.
- **Outputs:** `outputs/contract_gate/contract_gate_result.json`.
- **Artifact schema:** `contracts/schemas/contract_gate_result.schema.json`.
- **Fail-closed:** missing preflight artifact, non-zero preflight, invalid schema signal.
- **Mapped surfaces:** `scripts/run_contract_preflight.py`, `scripts/run_contract_enforcement.py`, contract tests.
- **Invariants protected:** schema authority, contract compatibility, fail-closed preflight.
- **Pass summary example:** `status=allow reason_codes=[CONTRACT_PREFLIGHT_PASS]`.
- **Fail summary example:** `status=block root_cause=run_contract_preflight returned non-zero`.

## 2) Runtime Test Gate
- **Purpose:** Execute selected runtime tests with enforced fallback smoke coverage.
- **Inputs:** changed paths, selection policy, baseline smoke inventory.
- **Outputs:** `outputs/test_selection_gate/test_selection_gate_result.json`, `outputs/runtime_test_gate/runtime_test_gate_result.json`.
- **Artifact schemas:** `test_selection_gate_result.schema.json`, `runtime_test_gate_result.schema.json`.
- **Fail-closed:** empty governed selection, invalid selected target, pytest failure.
- **Mapped surfaces:** `pr-pytest` execution, pytest and Jest runtime suites.
- **Invariants protected:** required eval coverage, control signals, replay/lineage smoke checks.
- **Pass summary example:** `status=allow selected_tests>0`.
- **Fail summary example:** `status=block failure_class=selection_integrity_failure`.

## 3) Governance Gate
- **Purpose:** Enforce registry/governance/required-check integrity.
- **Inputs:** system registry, governance policy docs, required-check policy.
- **Outputs:** `outputs/governance_gate/governance_gate_result.json`.
- **Artifact schema:** `contracts/schemas/governance_gate_result.schema.json`.
- **Fail-closed:** missing governance evidence, required-check mismatch, registry guard failure.
- **Mapped surfaces:** `run_system_registry_guard.py`, `run_required_check_alignment_audit.py`, governance tests.
- **Invariants protected:** control authority boundaries, required checks, governance manifest integrity.

## 4) Certification Gate
- **Purpose:** Validate promotion-readiness evidence (replay, lineage, done certification).
- **Inputs:** upstream gate artifacts, certification artifacts, replay/lineage tests.
- **Outputs:** `outputs/certification_gate/certification_gate_result.json`.
- **Artifact schema:** `contracts/schemas/certification_gate_result.schema.json`.
- **Fail-closed:** missing required artifacts, failed done-certification command, replay/lineage mismatch.
- **Mapped surfaces:** `run_done_certification.py`, replay/lineage/promotion tests.
- **Invariants protected:** certification discipline and promotion gating.

## PR Gate Orchestrator
- **Purpose:** execute gates in canonical order, aggregate results.
- **Output:** `outputs/pr_gate/pr_gate_result.json` (`contracts/schemas/pr_gate_result.schema.json`).
- **Constraint:** no policy logic; only invokes gate scripts and aggregates status.

## Gate order
`Contract Gate -> Test Selection Gate -> Runtime Test Gate -> Governance Gate -> Certification Gate`.
