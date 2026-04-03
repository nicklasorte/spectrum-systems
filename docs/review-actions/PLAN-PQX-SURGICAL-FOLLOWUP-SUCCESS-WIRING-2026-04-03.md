# Plan — PQX Surgical Follow-Up Success Wiring — 2026-04-03

## Prompt type
PLAN

## Roadmap item
Post-MVP red-team remediation follow-up (success-path completion rewiring)

## Intent
Repair regressions introduced by hardening so legitimate post-enforcement ALLOW paths finalize as success (`complete`/`completed`/exit 0), while preserving fail-closed hardening boundaries.

## Regressions being fixed
- `tests/test_pqx_backbone.py::test_runner_persists_artifacts_and_state_on_success` (`running` vs expected `complete`).
- `tests/test_pqx_fix_execution.py::test_bundle_resumes_correctly_after_fixes` (`blocked` vs expected `completed`).
- `tests/test_pqx_sequence_runner.py::test_sequence_runner_persists_bundle_state_when_configured` (missing second completed step).
- `tests/test_prompt_queue_sequence_cli.py::test_cli_success_returns_zero_and_writes_state` (exit 2 vs expected 0).

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-SURGICAL-FOLLOWUP-SUCCESS-WIRING-2026-04-03.md | CREATE | Required PLAN artifact before multi-file BUILD |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Add explicit post-enforcement success confirmation seam without restoring premature completion |
| spectrum_systems/modules/pqx_backbone.py | MODIFY | Rewire backbone entrypoint to use post-enforcement completion confirmation |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Rewire default slice executor to confirm completion after enforcement ALLOW |
| spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py | MODIFY | Rewire bundle default executor to same post-enforcement completion seam |

## Invariants to preserve
- Runner must not own final completion transition before enforcement authority.
- Block/review outcomes must not mark row complete.
- Explicit fixture decision mode only; no path/text sniffing.
- Explicit run identity; no trace-derived run_id fallback.
- Blocked-slice trace evidence invariant remains enforced.
- Enforcement timestamp override support remains available.

## Non-goals
- No architecture redesign of PQX runtime.
- No rollback of V-1/V-2/V-3/V-4/V-5 hardening.
- No schema/manifest changes unless strictly required.
- No test shortcuts that bypass runtime behavior.

## Risks
- Double-finalization bugs if completion confirmation is called in the wrong seam.
- Divergent success semantics if only some default executors are rewired.
- Caller expectations on status payload shape may require careful compatibility handling.

## Acceptance criteria
- Backbone success path persists row status `complete` only after enforcement ALLOW.
- Bundle resume/fix success path returns `completed`.
- Sequence runner persists both successful completed step IDs.
- Prompt-queue sequence CLI returns exit code `0` on successful post-enforcement completion.
- Hardening tests for V-1..V-5 still pass.

## Test plan
1. `pytest tests/test_pqx_backbone.py::test_runner_persists_artifacts_and_state_on_success`
2. `pytest tests/test_pqx_fix_execution.py::test_bundle_resumes_correctly_after_fixes`
3. `pytest tests/test_pqx_sequence_runner.py::test_sequence_runner_persists_bundle_state_when_configured`
4. `pytest tests/test_prompt_queue_sequence_cli.py::test_cli_success_returns_zero_and_writes_state`
5. `pytest tests/test_pqx_slice_runner.py tests/test_pqx_sequential_loop.py tests/test_enforcement_engine.py`
6. `pytest tests/test_pqx_backbone.py tests/test_pqx_fix_execution.py tests/test_pqx_sequence_runner.py tests/test_prompt_queue_sequence_cli.py`
7. `PLAN_FILES='docs/review-actions/PLAN-PQX-SURGICAL-FOLLOWUP-SUCCESS-WIRING-2026-04-03.md spectrum_systems/modules/runtime/pqx_slice_runner.py spectrum_systems/modules/pqx_backbone.py spectrum_systems/modules/runtime/pqx_sequence_runner.py spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py' .codex/skills/verify-changed-scope/run.sh`
