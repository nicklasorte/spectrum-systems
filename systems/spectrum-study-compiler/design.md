# Spectrum Study Compiler — Design (SYS-004)

## Role
Acts as a compiler for study artifacts: ingest normalized inputs, run validation and transformation passes, and emit a packaged deliverable with explicit diagnostics.

## Compiler Passes (initial)
1. **Intake**: Validate input schemas, check presence of provenance/run manifests, and verify revision lineage.
2. **Normalization**: Ensure consistent units, scenario labels, and identifiers across artifacts.
3. **Linking**: Attach assumptions, simulation runs, and precedent references to each artifact; verify `derived_from` completeness.
4. **Validation**: Apply rule packs to enforce mandatory fields, template adherence, and cross-artifact consistency; classify findings as warnings vs. errors.
5. **Packaging**: Assemble tables/figures/narratives into a bundle with report anchors; produce compiler manifest listing passes and outcomes.
6. **Emission**: Emit compiled outputs only if errors are zero; propagate warnings and unresolved items to reviewers.

## Inputs
- Study artifacts and narratives from SYS-003 with provenance.
- Assumption registry entries and precedent references as needed.
- Templates and packaging rules.

## Outputs
- Validated artifacts bundle with manifest and diagnostics.
- Warning/error report for reviewers.
- Updated lineage references for downstream decision artifacts.

## Failure Modes
- Missing or inconsistent manifests across inputs.
- Cross-artifact conflicts (scenario or unit mismatches).
- Dropped provenance/`derived_from` references during packaging.
- Non-deterministic ordering or formatting between runs.

## Human Review Points
- Review unresolved warnings before publication.
- Approve cross-artifact consistency decisions.
- Confirm that dropped artifacts and reasons are documented.

## Dependencies
- Relies on SYS-003 producing schema-valid artifacts with complete provenance.
- Uses `schemas/provenance-schema.json` to enforce lineage and reproducibility.
- Packaging rules should align with report assembly workflows in implementation repos.
