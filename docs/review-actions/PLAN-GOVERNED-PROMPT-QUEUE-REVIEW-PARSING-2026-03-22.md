# Plan — Governed Prompt Queue Review Parsing — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Prompt slice (governed prompt queue): review artifact parsing + structured findings extraction

## Objective
Add a fail-closed, provider-aware review markdown parser that emits schema-validated findings artifacts and deterministically attaches findings references to governed prompt queue work items.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REVIEW-PARSING-2026-03-22.md | CREATE | Record execution scope before BUILD work. |
| PLANS.md | MODIFY | Register this new plan in the active plans table. |
| contracts/schemas/prompt_queue_review_findings.schema.json | CREATE | Contract-first schema for normalized parsed review findings artifacts. |
| contracts/examples/prompt_queue_review_findings.json | CREATE | Golden-path example for findings artifact validation. |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add findings reference field and findings-parsed status support. |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Keep embedded work-item contract aligned with findings reference/state. |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Align example with updated work-item contract fields. |
| contracts/examples/prompt_queue_state.json | MODIFY | Align queue-state example embedded work item with updated contract fields. |
| contracts/standards-manifest.json | MODIFY | Register findings contract and bump manifest version metadata. |
| spectrum_systems/modules/prompt_queue/review_parser.py | CREATE | Pure markdown section parsing and fail-closed required-section checks. |
| spectrum_systems/modules/prompt_queue/findings_normalizer.py | CREATE | Provider-aware normalization into canonical structured findings artifact. |
| spectrum_systems/modules/prompt_queue/findings_artifact_io.py | CREATE | Findings artifact schema validation and machine-readable artifact emission. |
| spectrum_systems/modules/prompt_queue/findings_queue_integration.py | CREATE | Pure queue/work-item attachment logic for findings artifacts. |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add findings-related work-item fields/state enum support. |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Add deterministic transition support for findings parsing completion state. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export new parser/normalizer/IO/attachment entry points. |
| scripts/run_prompt_queue_review_parse.py | CREATE | Thin CLI to parse committed review markdown and update queue work item. |
| tests/fixtures/prompt_queue_reviews/claude_pass_review.md | CREATE | Deterministic fixture for Claude PASS parsing coverage. |
| tests/fixtures/prompt_queue_reviews/claude_fail_review.md | CREATE | Deterministic fixture for Claude FAIL parsing coverage. |
| tests/fixtures/prompt_queue_reviews/codex_fail_review.md | CREATE | Deterministic fixture for Codex FAIL parsing coverage. |
| tests/fixtures/prompt_queue_reviews/fail_missing_critical_findings.md | CREATE | Deterministic fail-closed missing-section fixture. |
| tests/fixtures/prompt_queue_reviews/fail_missing_required_fixes.md | CREATE | Deterministic fail-closed missing-section fixture. |
| tests/fixtures/prompt_queue_reviews/missing_decision.md | CREATE | Deterministic fail-closed missing decision fixture. |
| tests/fixtures/prompt_queue_reviews/missing_failure_mode_summary.md | CREATE | Deterministic fail-closed missing section fixture. |
| tests/test_prompt_queue_review_parsing.py | CREATE | Focused parser, normalization, schema, and queue attachment tests. |
| tests/test_prompt_queue_mvp.py | MODIFY | Align prompt queue MVP tests with new findings state/field contract updates. |
| docs/reviews/governed_prompt_queue_review_parsing_report.md | CREATE | Delivery artifact documenting architecture, guarantees, tests, and gaps. |

## Contracts touched
- prompt_queue_review_findings (new)
- prompt_queue_work_item (additive)
- prompt_queue_state (embedded work-item shape alignment)
- standards_manifest (version metadata + new contract entry)

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_review_parsing.py`
2. `pytest -q tests/test_prompt_queue_mvp.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not implement repair prompt generation.
- Do not create child repair work items.
- Do not add semantic ranking/deduplication for findings.
- Do not implement dependency scheduling or queue parallelism.
- Do not add live Claude/Codex API integration.

## Dependencies
- docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-MVP-2026-03-22.md (existing queue baseline contracts/module).
