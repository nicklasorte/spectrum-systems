# Plan — CTX-01-EXEC — 2026-04-18

## Prompt type
BUILD

## Roadmap item
CTX-01-EXEC — Context Bundle + Admission Control (Governed Context Layer)

## Objective
Implement a governed, versioned context bundle and fail-closed context admission layer for WPG execution with contradiction/freshness/provenance enforcement, red-team coverage, and readiness integration.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/context_bundle_artifact.schema.json | CREATE | Canonical schema for governed context bundle artifact. |
| contracts/examples/context_bundle_artifact.json | CREATE | Golden example for context bundle artifact validation. |
| contracts/schemas/context_admission_result.schema.json | CREATE | Canonical schema for admission outcome with blocking/freeze semantics. |
| contracts/examples/context_admission_result.json | CREATE | Golden example for context admission result validation. |
| contracts/standards-manifest.json | MODIFY | Register new governed contracts and bump manifest version metadata. |
| spectrum_systems/modules/wpg/context_governance.py | CREATE | Implement context bundle composition, admission policy, contradiction/freshness/provenance checks, red-team generation, and readiness gate integration. |
| spectrum_systems/orchestration/wpg_pipeline.py | MODIFY | Attach context bundle to pipeline input, enforce admission pre-execution, bind to readiness gate and artifact chain. |
| tests/fixtures/wpg/sample_workflow_loop_input.json | MODIFY | Provide governed context input fixture for CLI/global validation path. |
| tests/test_context_bundle_artifact.py | CREATE | Validate context bundle artifact schema and fail-closed required component behavior. |
| tests/test_context_admission_policy.py | CREATE | Validate admission policy completeness/freshness/contradiction/provenance decisions. |
| tests/test_context_contradiction_detection.py | CREATE | Validate cross-source contradiction detection and unresolved contradiction blocking. |
| tests/test_context_freshness.py | CREATE | Validate source freshness classification and stale critical freeze behavior. |
| tests/test_redteam_context_failures.py | CREATE | Validate adversarial context failure generation and detections. |
| tests/test_context_regressions.py | CREATE | Bind fixes to regression tests for repeated failure class blocking behavior. |
| tests/test_context_readiness_integration.py | CREATE | Validate readiness gate blocks promotion when context admission fails. |

## Contracts touched
- `context_bundle_artifact` (new)
- `context_admission_result` (new)
- `contracts/standards-manifest.json` version + contract registry entries

## Tests that must pass after execution
1. `python -m pytest -q tests/test_context_bundle_artifact.py`
2. `python -m pytest -q tests/test_context_admission_policy.py`
3. `python -m pytest -q tests/test_context_contradiction_detection.py`
4. `python -m pytest -q tests/test_context_freshness.py`
5. `python -m pytest -q tests/test_redteam_context_failures.py`
6. `python -m pytest -q tests/test_context_regressions.py`
7. `python scripts/run_contract_enforcement.py`
8. `python scripts/run_wpg_pipeline.py --input tests/fixtures/wpg/sample_workflow_loop_input.json`

## Scope exclusions
- Do not redesign unrelated WPG stages.
- Do not remove or weaken existing fail-closed controls.
- Do not introduce network-dependent runtime behavior.

## Dependencies
- Existing WPG pipeline and contract loader infrastructure remain authoritative inputs.
