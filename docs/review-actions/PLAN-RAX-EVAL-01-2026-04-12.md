# PLAN — RAX-EVAL-01 (2026-04-12)

Primary prompt type: BUILD

## Scope
Build a governed, fail-closed RAX eval surface so RAX execution does not advance on tests alone.

## Canonical alignment
- Preserve artifact-first execution.
- Preserve fail-closed behavior.
- Preserve promotion requires certification.
- Keep control authority external; emit bounded readiness artifact only.

## Planned file changes
| File | Action | Purpose |
| --- | --- | --- |
| docs/review-actions/PLAN-RAX-EVAL-01-2026-04-12.md | CREATE | Written plan required before touching more than two files. |
| contracts/schemas/eval_result.schema.json | MODIFY | Extend governed eval_result to carry deterministic signals/reason codes/runner identity needed by RAX eval execution. |
| contracts/schemas/eval_summary.schema.json | MODIFY | Extend governed eval_summary with required-eval coverage and explicit missing-eval failure signaling. |
| contracts/schemas/rax_eval_registry.schema.json | CREATE | Define governed registry artifact for required/optional RAX eval definitions. |
| contracts/schemas/rax_control_readiness_record.schema.json | CREATE | Define bounded RAX readiness artifact for downstream control consumption. |
| contracts/examples/rax_eval_registry.json | CREATE | Canonical example registry with all required RAX eval definitions and examples linkage. |
| contracts/examples/rax_control_readiness_record.json | CREATE | Canonical readiness example with fail-closed semantics. |
| contracts/standards-manifest.json | MODIFY | Register and version new/updated governed contracts. |
| config/policy/rax_eval_policy.json | CREATE | Repo-native deterministic policy for required eval IDs and fail-closed defaults. |
| spectrum_systems/modules/runtime/rax_eval_runner.py | CREATE | Deterministic RAX eval execution and eval_result/eval_summary emission. |
| spectrum_systems/modules/runtime/rax_assurance.py | MODIFY | Add bounded control-readiness evaluation from eval artifacts. |
| tests/test_rax_eval_runner.py | CREATE | Deterministic regression tests for eval definitions, eval cases, fail-closed missing-eval enforcement, and readiness blocking. |
| tests/test_rax_interface_assurance.py | MODIFY | Wire targeted readiness assertions for RAX assurance surface continuity. |
| docs/architecture/rax_eval_surface.md | CREATE | Concise authority-chain documentation for tests -> eval artifacts -> readiness artifact -> downstream control. |

## Validation plan
1. `pytest tests/test_rax_eval_runner.py tests/test_rax_interface_assurance.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py tests/test_contract_bootstrap.py`
3. `python scripts/run_contract_enforcement.py`

## Non-goals
- No redesign of global control authority.
- No unrelated refactors outside RAX eval surface and required contract wiring.
