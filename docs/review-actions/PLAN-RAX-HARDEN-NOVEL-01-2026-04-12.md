# PLAN — RAX-HARDEN-NOVEL-01 (2026-04-12)

Primary prompt type: BUILD

## Scope
Close only the remaining `novel_adversarial_pattern` seam in `RAX-REDTEAM-ARCH-01` by tightening semantic input assurance and wiring the failure into governed failure/eval/adversarial regression surfaces.

## File plan (surgical)
| File | Change | Purpose |
| --- | --- | --- |
| `spectrum_systems/modules/runtime/rax_assurance.py` | MODIFY | Add generalized semantic intent guard for ambiguity/evidence-avoidance execution language so novel adversarial intent fails closed. |
| `tests/test_rax_interface_assurance.py` | MODIFY | Add permanent regression tests for exact novel pattern + nearby variant to ensure `passed=false`, explicit `failure_classification`, and `stop_condition_triggered=true`. |
| `contracts/examples/rax_eval_case_set.json` | MODIFY | Add governed eval case for novel adversarial semantic pattern. |
| `docs/reviews/rax_failure_pattern_novel_adversarial_pattern.json` | CREATE | Failure-pattern artifact with minimal reproducer and semantic gap classification. |
| `docs/reviews/rax_novel_adversarial_design_note_2026-04-12.md` | CREATE | Concise review note documenting the semantic blind spot and fix rationale. |
| `docs/reviews/rax_adversarial_seed_patterns.json` | MODIFY/CREATE | Add seed/pattern class so lightweight adversarial generation replays this class. |

## Validation plan
1. `pytest tests/test_rax_interface_assurance.py -k "novel_adversarial orambiguity_or_minimal_proof" -q`
2. `pytest tests/test_rax_interface_assurance.py -q`
3. `pytest tests/test_rax_eval_runner.py -q`
4. `python scripts/run_rax_redteam_arch_01.py` and verify `novel_adversarial_pattern` is blocked.

## Constraints honored
- No new authority surfaces.
- No roadmap expansion/redesign.
- Fail-closed behavior only.
- Artifact-backed and trace-linked updates.
