# Plan — BATCH-SYS-ENF-04C — 2026-04-09

## Prompt type
BUILD

## Roadmap item
[BATCH-SYS-ENF-04C] Repair duplicate refs_attempted in contract preflight artifact

## Objective
Fix contract preflight artifact construction so `trace.refs_attempted` is deduplicated in insertion order while preserving schema strictness (`uniqueItems: true`) and full distinct attempted refs.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-SYS-ENF-04C-2026-04-09.md | CREATE | Plan-first artifact for targeted preflight artifact repair. |
| scripts/run_contract_preflight.py | MODIFY | Deduplicate refs_attempted in stable first-seen order before artifact emission. |
| tests/test_contract_preflight.py | MODIFY | Add focused regression test for duplicate refs_attempted collapse + order preservation + schema-valid artifact output. |

## Validation steps
1. `pytest tests/test_contract_preflight.py -k refs_attempted`
2. `pytest tests/test_contract_preflight.py`
