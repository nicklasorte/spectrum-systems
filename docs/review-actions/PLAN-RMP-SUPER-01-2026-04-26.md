# Plan — RMP-SUPER-01 — 2026-04-26

## Prompt type
PLAN

## Roadmap item
RMP-SUPER-01

## Objective
Build a fail-closed roadmap governance control system that requires machine-readable authority, realization evidence, dependency-valid progression, red-team/fix/re-validation loops, and attestation output artifacts.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RMP-SUPER-01-2026-04-26.md | CREATE | Required plan-first artifact for multi-file BUILD scope. |
| spectrum_systems/modules/runtime/rmp/__init__.py | CREATE | Module namespace for RMP governance controls. |
| spectrum_systems/modules/runtime/rmp/rmp_authority_sync.py | CREATE | Authority source-of-truth synchronization and drift detection. |
| spectrum_systems/modules/runtime/rmp/rmp_mirror_validator.py | CREATE | Markdown mirror validation against roadmap JSON authority. |
| spectrum_systems/modules/runtime/rmp/rmp_rfx_bridge.py | CREATE | Reconcile RFX roadmap entries and detect orphan/mismatch state. |
| spectrum_systems/modules/runtime/rmp/rmp_status_realizer.py | CREATE | Evidence-bound status realization checks. |
| spectrum_systems/modules/runtime/rmp/rmp_dependency_validator.py | CREATE | Dependency graph, bypass, and circular dependency gate validation. |
| spectrum_systems/modules/runtime/rmp/rmp_pre_h01_gate.py | CREATE | Pre-H01 gate for BLF-01, RFX-04, and sync prerequisites. |
| spectrum_systems/modules/runtime/rmp/rmp_drift_reporter.py | CREATE | Machine-readable drift report artifact emitter. |
| spectrum_systems/modules/runtime/rmp/rmp_rfx_placement.py | CREATE | Canonical RFX LOOP-09/10 placement gate validation. |
| spectrum_systems/modules/runtime/rmp/rmp_met_gate.py | CREATE | MET gate requiring Fix Integrity Proof. |
| spectrum_systems/modules/runtime/rmp/rmp_hop_gate.py | CREATE | HOP gate requiring MET measurement artifact. |
| scripts/run_rmp_attestation.py | CREATE | End-to-end control loop runner with red-team/fix/re-validation and attestation output. |
| tests/test_rmp_authority.py | CREATE | Authority sync, mirror, and RFX reconciliation coverage. |
| tests/test_rmp_dependency.py | CREATE | Dependency engine and status realization coverage. |
| tests/test_rmp_redteam_loops.py | CREATE | Red-team/fix/re-validation loop attestation coverage. |
| tests/test_rmp_gate_validation.py | CREATE | MET/HOP/H01 gate validation coverage. |
| artifacts/rmp_01_delivery_report.json | CREATE | Required final delivery artifact with governance guarantees and readiness state. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/run_rmp_attestation.py`
2. `python -m pytest tests/ -q -k rmp`
3. `python scripts/run_authority_shape_preflight.py --changed-files spectrum_systems/modules/runtime/rmp/rmp_authority_sync.py spectrum_systems/modules/runtime/rmp/rmp_mirror_validator.py spectrum_systems/modules/runtime/rmp/rmp_rfx_bridge.py spectrum_systems/modules/runtime/rmp/rmp_status_realizer.py spectrum_systems/modules/runtime/rmp/rmp_dependency_validator.py spectrum_systems/modules/runtime/rmp/rmp_pre_h01_gate.py spectrum_systems/modules/runtime/rmp/rmp_drift_reporter.py spectrum_systems/modules/runtime/rmp/rmp_rfx_placement.py spectrum_systems/modules/runtime/rmp/rmp_met_gate.py spectrum_systems/modules/runtime/rmp/rmp_hop_gate.py scripts/run_rmp_attestation.py tests/test_rmp_authority.py tests/test_rmp_dependency.py tests/test_rmp_redteam_loops.py tests/test_rmp_gate_validation.py --strict`

## Scope exclusions
- Do not introduce manual override or bypass behavior.
- Do not modify unrelated runtime systems outside the new `runtime/rmp` module set.
- Do not change ownership in `docs/architecture/system_registry.md`.

## Dependencies
- `contracts/examples/system_roadmap.json` remains the machine-readable authority input.
- Existing roadmap mirror and RFX cross-system roadmap documents remain mirrors, not authority artifacts.
