# PRL-01 PR Repair Loop Red-Team

## must_fix
- Attempt 3 bypass risk -> blocked in code and schema.
- Unknown failure auto-repair risk -> forced human_review_required.
- Test weakening/deletion risk -> tests_weakened=false const and blocked execution status.
- Schema weakening risk -> no schema edits outside new artifacts.
- Authority guard suppression risk -> explicit authority refs required in execution record.
- Missing CDE authorization risk -> authorization artifact mandatory before execution.
- Missing PQX evidence risk -> pqx_execution_ref required.
- Out-of-scope files risk -> bounded_files and authorized_files only.
- Flaky/infra as code-failure risk -> unknown_failure path to human review.
- Repeat failures not escalated risk -> attempt 2 unresolved => human_review_required.
- Hidden original failure risk -> attempt summary includes remaining_failure.
- Auto-push workflow risk -> no auto-push added.
- MET/RIL/FRE authority inflation risk -> observation-only wording used.

## should_fix
- Expand classifiers for richer local log parsing.

## observation
- Initial slice is artifact-first dry-run by default.
