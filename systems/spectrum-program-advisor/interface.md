# Spectrum Program Advisor — Interface (SYS-005)

## Purpose
Normalize canonical study artifacts into a coherent program-state model and emit deterministic, decision-ready outputs with explicit traceability and review gates.

## Inputs
- Working paper metadata aligned to `contracts/schemas/working_paper_input.schema.json`.
- Comment resolution matrix metadata aligned to `contracts/schemas/comment_resolution_matrix.schema.json` plus spreadsheet contract headers for intake validation.
- Meeting minutes metadata aligned to `contracts/meeting_minutes_contract.yaml`.
- Risk register, milestone plan, decision log, and assumption register aligned to new canonical contracts in `contracts/schemas/`.
- Optional context: prior agendas, issue backlogs, precedent library references (`schemas/precedent-schema.json`), and provenance records.

## Schemas Used
- `contracts/schemas/program_brief.schema.json`
- `contracts/schemas/study_readiness_assessment.schema.json`
- `contracts/schemas/next_best_action_memo.schema.json`
- `contracts/schemas/decision_log.schema.json`
- `contracts/schemas/risk_register.schema.json`
- `contracts/schemas/assumption_register.schema.json`
- `contracts/schemas/milestone_plan.schema.json`
- `contracts/schemas/provenance_record.schema.json`

## Outputs
- Program Brief (`program_brief`) with decision readiness status, top risks by required categories, open decisions, missing artifacts, and recommended next steps.
- Study Readiness Assessment (`study_readiness_assessment`) with gate checks, dependency-aware milestone status, and missing-evidence report.
- Next Best Action Memo (`next_best_action_memo`) listing prioritized actions with decision, risk, assumption, and milestone linkages.
- Top risks summary (derived view of `risk_register`) and open decisions summary (derived view of `decision_log`).
- Missing Evidence / Missing Artifact report (subset of readiness assessment `missing_evidence` + `artifact_status` gaps).

## Normalization Rules
- Treat decision readiness as the primary evaluation dimension; every output must carry a readiness status and numeric score where applicable.
- Risk categories must map to the canonical set: technical, data, schedule, stakeholder, process/legal, coordination, narrative.
- Milestones must include dependency status; readiness cannot exceed the least-ready blocking dependency.
- Assumptions are first-class; decisions and risks must reference them when applicable.
- Traceability is mandatory: every summary element must link back to source artifacts using `source_artifacts` and `source_reference` fields.
- Deterministic ordering: risks sorted by exposure score desc, decisions by needed-by date asc, actions by priority and due date.

## Human Review Points
- Validation of input contract compliance (schema + spreadsheet headers).
- Confirmation of readiness scoring and blockers.
- Review of recommended actions and decision implications before circulation to governance.

## Evaluation Method
- Contract-level validation for every output artifact.
- Determinism checks across runs given identical inputs.
- Spot comparisons against fixtures in `examples/spectrum-program-advisor/examples/outputs/` for regression.
- Governance alignment checks: ensure risk categories, decision types, and milestone gates match required enumerations.

## Versioning
- Interface version tracked via contract schema versions (`schema_version`) and standards release (`standards_version`).
- Breaking interface changes require schema version bump, updated fixtures, and evaluation reruns before implementation changes land downstream.
