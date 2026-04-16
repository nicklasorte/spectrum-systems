# HNX-01 Fix Pack 2 — Replay + Continuity Integrity Hardening

## Closure status
All Review 2 findings closed.

## Applied fixes
- Added stale checkpoint and trace-linkage checks in checkpoint/resume integrity.
- Added hidden-state variance detection in replay validation.
- Added observability metrics in `hnx_harness_effectiveness_record` computation.
- Added integration tests for stale checkpoint rejection and hidden-state variance.

## Regression mapping
- stale resume artifact -> `test_harness_eval_checkpoint_resume_and_readiness_fail_closed`
- hidden-state dependence -> `test_hidden_state_variance_detection_blocks`
