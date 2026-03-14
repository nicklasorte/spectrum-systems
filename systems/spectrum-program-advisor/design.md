# Spectrum Program Advisor — Design (SYS-005)

## Processing Stages
1) **Ingest + validate** — Load canonical inputs (working paper metadata, comment resolution matrix metadata, meeting minutes metadata, risk register, milestone plan, decision log, assumption register). Validate each against its contract; fail fast on missing required artifacts.
2) **Normalize to program-state model** — Merge inputs into an internal state representation keyed by `program_id` with links between risks, decisions, milestones, and assumptions. Derive dependency graph for milestones and decisions.
3) **Readiness scoring** — Calculate decision readiness as the primary metric using gate status, blocking dependencies, missing evidence, and risk exposure. Enforce deterministic scoring rules before any AI assistance.
4) **Assessment + memo generation** — Produce deterministic structured outputs first (`program_brief`, `study_readiness_assessment`, `next_best_action_memo`, derived top-risk/open-decision summaries). AI-assisted phrasing is optional and must round-trip to the structured outputs without altering keys.
5) **Traceability + provenance** — Attach `source_artifacts` and `source_reference` entries for every summary element. Include `provenance_record` references when available.
6) **Review + publication** — Route outputs for human review; block publication if readiness gating fails or provenance is incomplete.

## Decision Readiness Rules
- Readiness is capped by the least-ready gate (validation, stakeholder alignment, evidence completeness).
- Risks tagged `blocks_decision` or assumptions flagged `blocking` reduce readiness; mitigation completion can raise it.
- Missing artifacts automatically degrade readiness and populate the missing-evidence report.
- Dependencies on milestones or decisions marked `blocked` or `not_started` reduce readiness in proportion to criticality.

## AI Assistance Boundaries
- AI can assist with narrative summaries, but the canonical truth is the structured JSON that must validate against contracts.
- Prompts should request schema-valid JSON first, with any prose rendered as deterministic Markdown derived from the JSON.
- Generated text must reference source IDs (decisions, risks, assumptions, milestones) rather than inventing new identifiers.

## Failure Modes & Mitigations
- **Input schema drift**: enforce schema validation and standards manifest pinning; reject mismatched schema versions.
- **Non-deterministic outputs**: lock ordering rules and hash model inputs; compare against fixtures during evaluation.
- **Missing traceability**: require `source_artifacts` and `source_reference` population; fail runs lacking references.
- **AI hallucinations**: limit AI use to templated prose after structured outputs pass validation; surface low-confidence sections for review.

## Implementation Notes
- Operational code should live in the `spectrum-program-advisor` repo; this repo provides contracts, scaffolding, and evaluation fixtures.
- Use the canonical risk categories, decision types, and milestone statuses defined in the contracts to avoid taxonomy drift.
- When converting spreadsheets (e.g., CRM) into the program-state model, preserve original identifiers and revision lineage.
