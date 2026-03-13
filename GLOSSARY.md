# Glossary

- **system**: An automation capability with a defined interface, evaluation plan, and outputs (lives under `systems/`).
- **workflow**: Ordered steps executed by a system; specified in `workflows/`.
- **artifact**: Structured output (table, figure, narrative, manifest) with provenance and review status.
- **schema**: Authoritative contract for the shape of inputs, intermediates, or outputs.
- **manifest**: Run-level record capturing inputs, configurations, versions, validation results, and reviewers.
- **provenance**: Lineage and responsibility metadata for an artifact (sources, derivations, agents, review).
- **reproducibility**: Ability to rerun a workflow with the same manifest and obtain the same outputs.
- **data class**: Structured category of records stored in the data lake.
- **record**: A single structured instance within a data class.
- **decision**: Documented conclusion derived from artifacts and analysis with traceable inputs.
