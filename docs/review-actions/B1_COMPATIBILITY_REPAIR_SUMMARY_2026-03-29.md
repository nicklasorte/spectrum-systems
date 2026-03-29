# B1 Compatibility Repair Summary — 2026-03-29

## Why the first B1 attempt failed
The first B1 cut made `docs/roadmap/system_roadmap.md` a non-parseable stub. Existing PQX and test consumers still parse that path for the roadmap table, dependency fields, and contract references. As a result, `tests/test_pqx_backbone.py` and `tests/test_roadmap_step_contract.py` failed fail-closed.

## Governing compatibility rule now
- `docs/roadmaps/system_roadmap.md` is the active editorial roadmap authority.
- `docs/roadmap/system_roadmap.md` is a required operational compatibility mirror until migration is complete.
- Mirror must keep parseable roadmap table header/rows and keep step-contract references so legacy consumers remain deterministic.

## What was repaired
- Restored parseable roadmap table + required references in `docs/roadmap/system_roadmap.md`.
- Updated authority docs to explicitly define the dual-surface transition model.

## Future migration slice
- Recommended follow-on: **B2-MIGRATE-PQX-ROADMAP-PATH**
- Goal: move PQX/runtime/tests to consume `docs/roadmaps/system_roadmap.md` directly, then retire compatibility-mirror requirement.
- Exit condition: all roadmap parser/runtime/tests pass with no dependency on `docs/roadmap/system_roadmap.md`.
