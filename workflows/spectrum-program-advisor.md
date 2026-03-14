# Spectrum Program Advisor Workflow (SYS-005)

## Goal
Provide decision-ready program guidance by normalizing canonical artifacts, scoring readiness, and emitting briefs, assessments, and prioritized actions.

## Inputs (canonical contracts)
- Working paper metadata (`working_paper_input`)
- Comment resolution matrix metadata (`comment_resolution_matrix` + spreadsheet headers)
- Meeting minutes metadata (`meeting_minutes_contract`)
- Risk register (`risk_register`)
- Milestone plan (`milestone_plan`)
- Decision log (`decision_log`)
- Assumption register (`assumption_register`)

## Steps
1) Validate all inputs against canonical schemas and standards manifest.
2) Normalize artifacts into a program-state model keyed by `program_id`; build dependency graph across decisions, milestones, risks, and assumptions.
3) Compute decision readiness (primary metric) using gate status, missing evidence, risk exposure, and dependency readiness.
4) Generate structured outputs:
   - `program_brief`
   - `study_readiness_assessment`
   - `next_best_action_memo`
   - Derived top-risks and open-decisions summaries
   - Missing evidence / missing artifact report
5) Render human-facing Markdown/DOCX from validated JSON without altering identifiers or ordering.
6) Collect provenance records and publish alongside outputs for review and archival.

## Outputs
- Program brief, readiness assessment, next-best-action memo (JSON + Markdown)
- Updated risk/decision/milestone/assumption linkages in the program-state model
- Validation log with schema results and determinism hash

## Human Review Gates
- Input validation results
- Readiness score justification and blocker list
- Recommended actions and decision implications
