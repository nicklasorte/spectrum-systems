# Spectrum Study Compiler Prompt (v1.0)

## Purpose
Guide AI-assisted checks that validate compiled artifact sets, surface missing dependencies, and assemble report-ready bundles without inventing content.

## Inputs
- Candidate artifact set aligned to `schemas/artifact-bundle.schema.json`.
- Compiler manifest draft and pass list aligned to `schemas/compiler-manifest.schema.json`.
- Provenance/run manifests and assumption registry references.
- Section ordering rules and packaging templates.

## Outputs
- Diagnostics aligned to `schemas/diagnostics.schema.json` with explicit warning/error entries.
- Completed ordering lists and bundle descriptors without altering quantitative content.
- Reviewer-ready notes that explain warnings vs. errors and required follow-ups.

## Behaviors
- Validate that every artifact references required provenance, manifests, and assumption/precedent IDs; flag missing optional links as warnings.
- Detect missing dependencies (e.g., absent run manifest, section template, or assumption entry) and classify severity based on rule packs.
- Generate diagnostics with codes, severities, artifact/section references, and suggested remediation steps.
- Assemble report-ready bundles strictly from supplied artifacts; never fabricate sections, metrics, or values.
- Propagate warnings while blocking emission on errors; keep ordering deterministic and recorded.

## Constraints
- No speculative content: only summarize or reorder supplied artifacts.
- Do not change quantitative values, units, or metrics; highlight inconsistencies instead.
- Preserve provided ordering rules; if ties or ambiguity exist, emit an error and halt packaging.
- All outputs must cite manifest IDs, artifact IDs, section anchors, and provenance references.

## Diagnostics Rules
- **Errors**: missing provenance/run manifest, duplicate artifact or section IDs, absent required sections, unresolved checksum placeholders, undefined ordering rules.
- **Warnings**: missing optional assumptions or precedents, formatting deviations that do not change meaning, optional artifacts absent but acknowledged.
- Each diagnostic entry must include `code`, `severity`, `message`, `artifact_id` or `section_id`, and `suggested_action`.

## Review Handoff
- Provide a concise reviewer summary: blocking errors, warning count by category, and actions needed.
- Include hash/checksum placeholders for downstream verification and note which fields must be populated by implementation code.
