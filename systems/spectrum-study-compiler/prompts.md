# Prompts — Spectrum Study Compiler

The compiler primarily orchestrates artifacts produced by `prompts/report-drafting.md` but may invoke prompts for consistency checks or manifest summaries.

- **Purpose**: Apply deterministic checks and summaries while packaging study artifacts; ensure narratives remain aligned to compiled artifacts.
- **Inputs**: Normalized artifacts with provenance, run manifests, packaging rules, target report structure.
- **Outputs**: Compiler manifest summaries, optional narrative adjustments, and validation messages tied to artifacts.
- **Constraints**: No speculative content; only reconcile or summarize provided artifacts; maintain deterministic ordering; propagate warnings/errors explicitly.
- **Grounding Rules**: Cite artifact IDs, run manifests, and assumptions; never alter quantitative values; highlight missing provenance instead of inferring.
- **Versioning**: Any compiler prompt or rule change must be versioned and reflected in the compiler manifest; rerun evaluation cases after changes.
