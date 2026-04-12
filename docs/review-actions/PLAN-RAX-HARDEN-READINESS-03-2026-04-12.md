# Plan — RAX-HARDEN-READINESS-03 — 2026-04-12

## Prompt type
BUILD

## Roadmap item
RAX-HARDEN-READINESS-03

## Objective
Make RAX control readiness a mandatory fail-closed gate that is recomputed from governed inputs and blocks advancement across all ten surviving red-team seams.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/rax_eval_runner.py | MODIFY | Implement mandatory readiness gating, governed recomputation, contradiction handling, trace/lineage checks, authority hardening, dependency and cross-run consistency enforcement. |
| spectrum_systems/modules/runtime/rax_assurance.py | MODIFY | Extend readiness wrapper to pass governed evidence inputs into recomputation logic. |
| tests/test_rax_eval_runner.py | MODIFY | Add permanent regression tests for the ten surviving attacks and readiness gate behavior. |
| scripts/run_rax_redteam_harness_01.py | MODIFY | Convert previously surviving seams into enforced, blocked scenarios and keep report aligned to hardened behavior. |
| docs/review-actions/RAX-HARDEN-READINESS-03-DESIGN-NOTE.md | CREATE | Document mandatory readiness gate and governed recomputation inputs. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_rax_eval_runner.py tests/test_rax_interface_assurance.py`
2. `python scripts/run_rax_redteam_harness_01.py`

## Scope exclusions
- Do not redesign the RAX architecture.
- Do not introduce broad realization/orchestration refactors outside readiness hardening.
- Do not modify unrelated contracts or non-RAX modules.

## Dependencies
- Existing RAX eval runner and assurance contracts must remain schema-valid.
