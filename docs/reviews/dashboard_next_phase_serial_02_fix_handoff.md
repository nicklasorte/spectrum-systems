# DASHBOARD-NEXT-PHASE-SERIAL-02 — Fix Handoff

## Prompt type
PLAN

## Narrow follow-up prompt
Implement only the remaining highest-leverage serial-02 blockers:
1. Expand action surface to governed non-decision actions with explicit audit records and non-bypass tests.
2. Add incident/postmortem panel drill-through links to concrete repair artifacts and postmortem references.
3. Extend simulator contract checks to enforce fixture-only scenario classes (`stale`, `partial`, `replay_mismatch`, `override_heavy`, `low_provenance`) with fail-closed rendering.

Constraints:
- no new dashboard authority
- no new 3-letter systems
- all additions must pass dashboard certification gate
- stop after writing/validating code and tests for these fixes
