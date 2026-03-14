# MVP Scope — spectrum-program-advisor

## Required Capabilities
1. Ingest canonical inputs: working paper metadata, comment resolution matrix metadata, meeting minutes metadata, risk register, milestone plan, decision log, assumption register.
2. Normalize into a shared program-state model with traceability across decisions, risks, assumptions, and milestones.
3. Produce deterministic structured outputs:
   - Program Brief
   - Study Readiness Assessment
   - Next Best Action Memo
   - Top Risks summary
   - Open Decisions summary
   - Missing Evidence / Missing Artifact report
4. Provide a simple CLI to surface outputs from fixtures.
5. Include fixtures and unit tests that validate against canonical contracts.

## Non-Goals (MVP)
- Full automation of ingestion or AI-heavy drafting; start with rule-based aggregation.
- Custom schemas; rely on `spectrum-systems` contracts.
- Non-deterministic outputs; prose is derived from validated JSON.

## Evaluation Gates
- Schema validation for every artifact.
- Determinism checks across runs.
- Readiness score justification with explicit blockers.
- Coverage of required risk categories.

## Dependencies
- `spectrum-systems` contracts and standards manifest.
- Upstream engines that produce canonical inputs.
- Human review for publication.
