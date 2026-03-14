# Prompt Governance Framework

Prompts in this repository are treated as governed artifacts with the same rigor as schemas and contracts. They must be deterministic, schema-aligned, and reviewable across the czar ecosystem.

## Scope
- All prompts under `prompts/` and system-specific prompt references in `systems/*/`.
- Prompts used in evaluation harnesses, readiness bundles, and operational engines governed by this control plane.

## Governance Requirements
- **Use the standard template**: Author new prompts with `prompts/prompt-template.md` to capture purpose, inputs, outputs, constraints, and example usage.
- **Align to schemas and contracts**: Declare the authoritative schemas and contracts the prompt depends on; never redefine schemas locally.
- **Version every change**: Maintain version headers in prompt files and update the registry in `prompts/README.md`. Follow `prompts/prompt-versioning.md` for numbering, changelogs, and review gates.
- **Determinism and provenance**: Specify grounding rules, validation steps, and run-manifest expectations so outputs can be audited and reproduced.

## Review and Lifecycle
- Prompts that affect system behavior or output shape **must undergo architecture review** using `docs/design-review-standard.md` before downstream adoption.
- Material changes require evaluation updates and, where applicable, reruns of readiness bundles or regression checks.
- Record decisions and rationale in `DECISIONS.md` or the relevant design review record when prompt updates change system interfaces or dependencies.

## Implementation Steps
1. Draft or update the prompt using `prompts/prompt-template.md`.
2. Note the version in the prompt header and log changes per `prompts/prompt-versioning.md`.
3. Update `prompts/README.md` and any system-specific prompt references under `systems/<system>/`.
4. Capture required tests/evaluations and human review gates before promoting the new version.
