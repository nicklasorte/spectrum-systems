# Spectrum Pipeline Engine

## Purpose
Orchestrate upstream engines into agenda packages and decision-readiness bundles without mutating canonical contracts.

## Steps
1. Validate all inputs against pinned contract versions and provenance requirements.
2. Build dependency graph across minutes, agenda seeds, comment matrices, and readiness artifacts.
3. Generate/refresh agenda aligned to `meeting_agenda_contract` with traceability to minutes and comments.
4. Normalize readiness artifacts (risk/decision/assumption/milestone) and assemble advisor-ready products.
5. Emit readiness bundle + agenda package + pipeline run manifest; block on validation or determinism failures.

## References
- Interface: `systems/spectrum-pipeline-engine/interface.md`
- Design: `systems/spectrum-pipeline-engine/design.md`
- Schemas/Contracts: `contracts/standards-manifest.json`
- Prompts: `systems/spectrum-pipeline-engine/prompts.md`
- Evaluation: `systems/spectrum-pipeline-engine/evaluation.md`
