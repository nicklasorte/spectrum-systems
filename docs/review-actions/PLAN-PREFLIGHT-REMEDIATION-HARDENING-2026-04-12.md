# PLAN — BUILD — PREFLIGHT REMEDIATION HARDENING — 2026-04-12

## Intent
Harden the existing governed preflight remediation execution path end-to-end by extending repo-native runtime, artifact contracts, and fail-closed enforcement without introducing a new subsystem.

## Scope
1. Bind remediation rerun to real `scripts/run_contract_preflight.py` production invocation path with deterministic seam support.
2. Add provenance-attested preflight execution evidence and enforce it in SEL before continuation/promotion.
3. Bind remediation lineage to admitted request + failure instance with digest continuity and freshness checks.
4. Harden CDE/TPA inputs with evidence digests and freshness windows.
5. Enforce strict scope digest matching and retry-stop behavior across missing/ambiguous/repeated branches.
6. Emit non-authoritative RIL/PRG diagnostics and replay-integrity artifacts.
7. Add negative/adversarial tests for bypass, replay, overscope, and missing evidence fail-closed behavior.

## Execution steps
- Update `spectrum_systems/modules/runtime/governed_repair_foundation.py` + schemas for CDE/TPA digest/freshness binding.
- Update `spectrum_systems/modules/runtime/governed_repair_loop_execution.py` for real preflight runner, execution record emission, lineage/failure-instance binding, and terminal hardening.
- Update `spectrum_systems/modules/runtime/system_enforcement_layer.py` for anti-replay, strict scope digest checks, retry hard-stops, and remediation evidence requirements.
- Update/add tests in `tests/test_governed_preflight_remediation_loop.py` for production-path, fail-closed negative scenarios, and non-authoritative outputs.
- Run focused pytest + contract tests; document implementation report.
