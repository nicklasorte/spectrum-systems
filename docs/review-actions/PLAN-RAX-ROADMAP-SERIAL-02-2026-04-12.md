# PLAN-RAX-ROADMAP-SERIAL-02-2026-04-12

## Prompt type
BUILD

## Intent
Implement and wire the remaining RAX roadmap seams (RAX-13 through RAX-22) on top of the existing RAX-03 through RAX-12 foundations, with fail-closed operational gating, external script wiring, and deterministic tests.

## Scoped files
| File | Action | Scope |
| --- | --- | --- |
| `spectrum_systems/modules/runtime/rax_eval_runner.py` | MODIFY | Add operational hard-gate enforcement helpers for CI/promotion wiring across RAX-13..RAX-22. |
| `scripts/run_rax_operational_gate.py` | ADD | Thin CLI for external operational path emission and fail-closed exit status. |
| `tests/test_rax_eval_runner.py` | MODIFY | Add deterministic tests for conflict-zero gate, replay/policy evidence binding, drift threshold freeze semantics, admission anti-poisoning, judgment compilation candidate, and signed provenance checks. |
| `tests/test_run_rax_operational_gate_cli.py` | ADD | CLI wiring test proving external operational seam enforces fail-closed boundary. |

## Validation plan
1. `pytest tests/test_rax_eval_runner.py tests/test_run_rax_operational_gate_cli.py`
2. `pytest tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
