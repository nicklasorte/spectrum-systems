# Plan — STRATEGY-SOURCE-GOVERNANCE-HARDENING — 2026-03-30

## Prompt type
PLAN

## Roadmap item
Grouped PQX slice — strategy/source authority enforcement for roadmap/review/progression seams

## Objective
Bind strategy and source authority into existing roadmap, review, and progression seams so strategy/source linkage becomes required, validated, and fail-closed.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-STRATEGY-SOURCE-GOVERNANCE-HARDENING-2026-03-30.md | CREATE | Required PLAN artifact before multi-file governance hardening |
| PLANS.md | MODIFY | Register this plan in active plans table |
| docs/architecture/system_strategy.md | CREATE | Canonical strategy authority and invariants reference |
| docs/architecture/system_source_index.md | CREATE | Canonical bounded source authority index for governance grounding |
| docs/architecture/strategy_guided_roadmap_prompt.md | CREATE | Structured roadmap-generation prompt with mandatory provenance |
| docs/governance/strategy_compliance_hard_gate.md | CREATE | Fail-closed yes/no progression hard gate checklist |
| CLAUDE_REVIEW_PROTOCOL.md | MODIFY | Add operational strategy/source and drift enforcement checks |
| docs/design-review-standard.md | MODIFY | Add required strategy/source compliance and drift sections |
| CODEX.md | MODIFY | Require strategy/source-grounded outputs and anti-duplication checks |
| CLAUDE.md | MODIFY | Require strategy/source-grounded review execution checks |
| spectrum_systems/modules/review_orchestrator.py | MODIFY | Enforce strategy/source linkage in review manifests at load-time |
| templates/review/claude_review_prompt_template.md | MODIFY | Surface strategy/source refs explicitly in generated review prompts |
| reviews/manifests/p_gap_detection.review.json | MODIFY | Add required strategy/source authority references |
| reviews/manifests/p1_slide_intelligence.review.json | MODIFY | Add required strategy/source authority references |
| reviews/manifests/q_working_paper.review.json | MODIFY | Add required strategy/source authority references |
| tests/test_review_orchestrator.py | MODIFY | Add coverage for strategy/source fail-closed manifest validation |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_review_orchestrator.py`
2. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-STRATEGY-SOURCE-GOVERNANCE-HARDENING-2026-03-30.md`

## Scope exclusions
- Do not redesign queue/cycle runner control logic.
- Do not introduce new governance subsystems outside existing review/roadmap/progression seams.
- Do not modify unrelated manifests, contracts, or runtime modules.

## Dependencies
- docs/roadmaps/system_roadmap.md remains the sole authoritative execution roadmap.
- Existing review orchestration seam (`spectrum_systems/modules/review_orchestrator.py`) remains the enforcement entry point.
