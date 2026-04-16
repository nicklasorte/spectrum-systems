# HNX-01 Fix Pack 1 — Boundary and Transition Hardening

## Closure status
All Review 1 findings closed.

## Applied fixes
- Added stricter transition policy checks for terminal-state and stop/freeze requirements.
- Expanded boundary forbiddance for promotion/policy/release authority names.
- Added regression tests in `tests/test_hnx_hardening.py` covering invalid transition insertion and authority smuggling.

## Regression mapping
- RT1-STAGE-BYPASS -> `test_deterministic_stage_machine_and_stage_skip_detector`
- Authority smuggling -> `test_boundary_fencing_blocks_forbidden_owner_overlap`
