# Plan — PQX-ROADMAP-ALIGN-01 — 2026-03-29

## Prompt type
PLAN

## Roadmap item
[ROW: PQX-ROADMAP-ALIGN-01] Align Queue and Protocol Roadmaps with Current Repo State

## Objective
Align roadmap documentation so queue/protocol/execution-map authority and status statements match the current repository state without changing runtime behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/roadmap/pqx_queue_roadmap.md | MODIFY | Align QUEUE-01..QUEUE-12 statuses with current implemented reality and keep QUEUE-13 planned. |
| docs/roadmap/pqx_protocol_hardening.md | MODIFY | Narrow PQX-PROT-11 so it is protocol-layer envelope scope and does not duplicate QUEUE-11 audit bundle. |
| docs/roadmap/pqx_execution_map.md | MODIFY | Reflect active execution tracks (Queue roadmap now, Protocol hardening follow-on). |
| docs/roadmap/README.md | MODIFY | Add explicit roadmap authority/subordination rule. |
| docs/roadmap/system_roadmap.md | MODIFY (if needed) | Add minimal matching authority clarification to avoid conflicting interpretation. |

## Contracts touched
None.

## Tests that must pass after execution
1. `git diff -- docs/roadmap/pqx_queue_roadmap.md docs/roadmap/pqx_protocol_hardening.md docs/roadmap/pqx_execution_map.md docs/roadmap/README.md docs/roadmap/system_roadmap.md`
2. `git diff --name-only`
3. `bash .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify runtime, schema, test, CLI, control-loop, or module code.
- Do not add or remove roadmap rows.
- Do not reorder roadmap rows or change dependencies.
- Do not introduce any alternate authoritative roadmap source.

## Dependencies
- Existing queue implementation slices through QUEUE-12 remain merged in repository history/evidence.
