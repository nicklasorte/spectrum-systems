# Next Recommended Slice

## BATCH-GOV-FIX-04 — Checker-Level External Path Regression Lock

Add direct checker tests that call `scripts.check_governance_compliance.evaluate_prompt_file()` with external temp-path files to guarantee:
- external valid prompt content passes,
- external invalid prompt content fails fail-closed,
- external-path handling remains crash-free.

### Outcome target
- Prevents future regressions in external path handling independent of wrapper behavior.
- Keeps governance preflight fail-closed and deterministic for both in-repo and out-of-repo prompt files.
