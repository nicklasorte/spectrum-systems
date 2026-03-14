# Architecture — spectrum-program-advisor

## Objective
Provide a program-management advisor that sits above existing operational engines and produces decision-ready guidance for spectrum studies.

## Components
- **Ingestion + validation**: Accept canonical inputs (working paper metadata, CRM metadata, meeting minutes metadata, risk register, decision log, milestone plan, assumption register) and validate against contracts from `spectrum-systems`.
- **Program-state model**: Normalize inputs into a unified graph keyed by `program_id`, linking risks ↔ decisions ↔ milestones ↔ assumptions ↔ evidence.
- **Readiness engine**: Compute decision readiness using gate status, dependency readiness, missing evidence, and risk exposure.
- **Advisory outputs**: Emit `program_brief`, `study_readiness_assessment`, `next_best_action_memo`, top risks summary, open decisions summary, and missing-evidence report. Structured JSON is canonical; Markdown/DOCX are renderings.
- **CLI**: Deterministic wrapper that surfaces advisory outputs from fixtures for testing and orchestration integration.

## Data flow
1. Validate inputs against contract schemas (see `contracts/README.md` for sources).
2. Normalize into the program-state model (see `docs/program-state-model.md`).
3. Score decision readiness and gate status.
4. Generate structured outputs and render human-facing summaries.
5. Record provenance and publish for review.

## Governance
- Contracts and standards live in `spectrum-systems`; this repo imports them and ships aligned fixtures.
- Risk categories are fixed: technical, data, schedule, stakeholder, process/legal, coordination, narrative.
- Determinism is required; any AI-assisted text must round-trip to validated JSON.
