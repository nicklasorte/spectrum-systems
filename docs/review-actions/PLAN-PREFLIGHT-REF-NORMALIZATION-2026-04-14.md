# Plan — PREFLIGHT-REF-NORMALIZATION — 2026-04-14

## Prompt type
BUILD

## Roadmap item
PREFLIGHT-REF-NORMALIZATION

## Objective
Fix push-event preflight ref mismatch failures by introducing one canonical, deterministic ref-normalization path shared by preflight wrapper build and preflight execution, with explicit failure classification and auto-repair-aware diagnostics.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PREFLIGHT-REF-NORMALIZATION-2026-04-14.md | CREATE | Required multi-file execution plan |
| spectrum_systems/modules/runtime/preflight_ref_normalization.py | CREATE | Canonical event-aware base/head normalization utility |
| scripts/build_preflight_pqx_wrapper.py | MODIFY | Use canonical normalization and emit ref observability artifact fields |
| scripts/run_contract_preflight.py | MODIFY | Use canonical normalization before changed-path resolution and include structured context in report/artifacts |
| spectrum_systems/modules/runtime/github_pr_autofix_contract_preflight.py | MODIFY | Distinguish bad-ref-resolution mismatch in diagnosis/repair classification |
| scripts/run_github_pr_autofix_contract_preflight.py | MODIFY | Normalize refs consistently for auto-repair reruns |
| tests/test_preflight_ref_normalization.py | CREATE | Unit tests for push/pr/workflow_dispatch/local ref normalization rules |
| tests/test_contract_preflight.py | MODIFY | Regression tests for push fallback, explicit override, workflow_dispatch block reason, and normalization observability |
| tests/test_github_pr_autofix_contract_preflight.py | MODIFY | Classification tests for missing/malformed/unsupported/bad-ref-resolution reasons |
| docs/governance/preflight_ref_normalization.md | CREATE | Canonical documentation for event-specific ref normalization + artifact fields |

## Contracts touched
None (classification distinction is encoded in deterministic reason codes under existing diagnosis schemas).

## Tests that must pass after execution
1. `pytest tests/test_preflight_ref_normalization.py tests/test_contract_preflight.py tests/test_github_pr_autofix_contract_preflight.py`
2. `python scripts/build_preflight_pqx_wrapper.py --base-ref "" --head-ref "" --output outputs/contract_preflight/preflight_pqx_task_wrapper.json`
3. `python scripts/run_contract_preflight.py --base-ref "" --head-ref "" --output-dir outputs/contract_preflight_push_ref_fix`

## Scope exclusions
- Do not relax fail-closed behavior when trustworthy refs cannot be derived.
- Do not change canonical system ownership in `docs/architecture/system_registry.md`.
- Do not introduce non-deterministic inference for ref normalization.

## Dependencies
- Existing changed-path resolution and preflight diagnosis/repair flows remain authoritative and are extended in place.
