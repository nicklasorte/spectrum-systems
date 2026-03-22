# Governed Prompt Queue Review Parsing Report

## Date
2026-03-22

## Scope
This patch delivers the next governed prompt queue slice for parsing committed review markdown artifacts into a normalized, schema-validated findings artifact, then deterministically attaching that findings artifact reference to a prompt queue work item.

Out of scope (intentionally deferred): repair prompt generation, child repair work-item creation, semantic ranking/deduplication, dependency scheduling, and live provider API integration.

## Files created/changed
- Plan + tracking:
  - `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REVIEW-PARSING-2026-03-22.md`
  - `PLANS.md`
- Contracts/examples:
  - `contracts/schemas/prompt_queue_review_findings.schema.json` (new)
  - `contracts/examples/prompt_queue_review_findings.json` (new golden-path)
  - `contracts/schemas/prompt_queue_work_item.schema.json` (add `findings_artifact_path`, `findings_parsed` status)
  - `contracts/schemas/prompt_queue_state.schema.json` (embedded work-item alignment)
  - `contracts/examples/prompt_queue_work_item.json`
  - `contracts/examples/prompt_queue_state.json`
  - `contracts/standards-manifest.json`
- Prompt queue module:
  - `spectrum_systems/modules/prompt_queue/review_parser.py`
  - `spectrum_systems/modules/prompt_queue/findings_normalizer.py`
  - `spectrum_systems/modules/prompt_queue/findings_artifact_io.py`
  - `spectrum_systems/modules/prompt_queue/findings_queue_integration.py`
  - `spectrum_systems/modules/prompt_queue/queue_models.py`
  - `spectrum_systems/modules/prompt_queue/queue_state_machine.py`
  - `spectrum_systems/modules/prompt_queue/__init__.py`
- CLI:
  - `scripts/run_prompt_queue_review_parse.py`
- Tests/fixtures:
  - `tests/fixtures/prompt_queue_reviews/*.md` (new deterministic parser fixtures)
  - `tests/test_prompt_queue_review_parsing.py`
  - `tests/test_prompt_queue_mvp.py` (contract-aligned coverage remains valid)
  - `tests/test_contracts.py`
  - `tests/test_contract_enforcement.py`

## Findings artifact schema summary
New contract `prompt_queue_review_findings` defines a deterministic normalized artifact with:
- source identity: `findings_artifact_id`, `work_item_id`, `source_review_artifact_path`
- provider context: `review_provider`, `fallback_used`, `fallback_reason`
- review outcomes: `review_decision`, `trust_assessment`, `failure_mode_summary`
- structured findings arrays (`critical_findings`, `required_fixes`, `optional_improvements`) with per-item fields:
  - `finding_id`, `summary`, `body`, `severity`, `file_references`, `source_section`
- raw preserved markdown section text under `raw_sections`
- parser lineage: `parsed_at`, `parser_version`

## Parser guarantees
- Provider-aware parsing for `claude` and `codex`.
- Section normalization tolerates minor markdown formatting variance (numbered headings, bolded values, etc.).
- Fail-closed enforcement:
  - missing/malformed Decision → parse error
  - FAIL without Critical Findings → parse error
  - FAIL without Required Fixes → parse error
  - missing Failure Mode Summary → parse error
- No missing required sections are silently invented.
- Raw section text is preserved for downstream repair-prompt construction.

## Queue integration behavior
- Work item contract extended with nullable `findings_artifact_path`.
- New deterministic state `findings_parsed` added with explicit transition `review_complete -> findings_parsed`.
- Queue attachment logic is pure and isolated in `findings_queue_integration.py`.
- CLI flow (`scripts/run_prompt_queue_review_parse.py`) is thin:
  1. load work item JSON,
  2. parse review markdown,
  3. normalize findings artifact,
  4. validate + emit findings JSON,
  5. update work-item findings reference + state,
  6. validate updated work item before write.

## Test evidence
Commands and exact pass/fail evidence are captured in the implementation delivery response.

## Remaining gaps
Deferred to later prompt slices:
1. repair prompt generation from parsed findings
2. automatic child repair work-item generation
3. semantic ranking/triage of findings
4. dependency-aware scheduling across queue graph
5. live Claude/Codex provider integration and retry policies
