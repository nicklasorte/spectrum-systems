# Governed Prompt Queue Repair Prompt Generation Report

## Date
2026-03-22

## Scope
This patch delivers the next governed prompt queue slice: deterministic repair prompt artifact generation from validated review findings artifacts for FAIL decisions, schema-backed artifact emission, and deterministic queue work-item attachment/state progression.

Out of scope (deferred): child repair work-item creation, automatic Codex execution, semantic ranking of multiple findings artifacts, dependency scheduling, queue parallelism, retry loops, and merge/close automation.

## Files created/changed
- Plan + tracking:
  - `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REPAIR-PROMPT-2026-03-22.md`
  - `PLANS.md`
- Contracts/examples:
  - `contracts/schemas/prompt_queue_repair_prompt.schema.json` (new)
  - `contracts/examples/prompt_queue_repair_prompt.json` (new golden-path)
  - `contracts/schemas/prompt_queue_work_item.schema.json` (add `repair_prompt_artifact_path`, `repair_prompt_generated`)
  - `contracts/schemas/prompt_queue_state.schema.json` (embedded work-item alignment)
  - `contracts/examples/prompt_queue_work_item.json`
  - `contracts/examples/prompt_queue_state.json`
  - `contracts/standards-manifest.json`
- Prompt queue module:
  - `spectrum_systems/modules/prompt_queue/repair_prompt_generator.py`
  - `spectrum_systems/modules/prompt_queue/repair_prompt_artifact_io.py`
  - `spectrum_systems/modules/prompt_queue/repair_prompt_queue_integration.py`
  - `spectrum_systems/modules/prompt_queue/queue_models.py`
  - `spectrum_systems/modules/prompt_queue/queue_state_machine.py`
  - `spectrum_systems/modules/prompt_queue/__init__.py`
- CLI:
  - `scripts/run_prompt_queue_repair_prompt.py`
- Tests:
  - `tests/test_prompt_queue_repair_prompt_generation.py`
  - `tests/test_prompt_queue_mvp.py`
  - `tests/test_contracts.py`

## Repair prompt artifact schema summary
New contract `prompt_queue_repair_prompt` defines required deterministic fields:
- identity and lineage: `repair_prompt_artifact_id`, `work_item_id`, `source_findings_artifact_path`, `source_review_artifact_path`
- provider audit chain: `review_provider`, `fallback_used`, `fallback_reason`
- decision/generation state: `review_decision` (const `FAIL`), `prompt_generation_status` (const `generated`)
- generated prompt payload: `prompt_scope_summary`, `prompt_text`
- bounded scope metadata: `required_fixes_count`, `critical_findings_count`, `likely_files`, `suggested_test_commands`, `bounded_not_in_scope`, `finding_ids_included`
- generator lineage: `generated_at`, `generator_version`

## Generator guarantees
- Fails closed for PASS findings decisions.
- Fails closed for malformed findings artifacts by validating findings schema before generation.
- Generates deterministic bounded sections: Motivation, Scope, Required fixes, Likely files, Tests, Implementation constraints, Not in scope, Mandatory delivery contract.
- Prioritizes required fixes and moves optional improvements into bounded not-in-scope context.
- Preserves `review_provider`, `fallback_used`, and `fallback_reason` from findings artifact to repair prompt artifact.
- Validates repair prompt artifact schema before write.
- Updates work item deterministically with `repair_prompt_artifact_path` and transition `findings_parsed -> repair_prompt_generated`.

## Test evidence
Executed:
- `pytest -q tests/test_prompt_queue_repair_prompt_generation.py tests/test_prompt_queue_review_parsing.py tests/test_prompt_queue_mvp.py`
- `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
- `python scripts/run_contract_enforcement.py`
- `.codex/skills/contract-boundary-audit/run.sh` (existing repository-wide warnings/failures surfaced)
- `PLAN_FILES='<declared files>' .codex/skills/verify-changed-scope/run.sh`

## Remaining gaps
Still intentionally deferred to future prompt slices:
1. automatic child repair work-item creation
2. automatic Codex repair execution
3. semantic ranking across multiple findings artifacts
4. dependency-aware scheduling
5. queue parallelism
6. retry-loop policy
7. merge/close lifecycle automation
