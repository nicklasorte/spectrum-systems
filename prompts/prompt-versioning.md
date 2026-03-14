# Prompt Versioning and Review

Prompt updates are governed to preserve determinism, reproducibility, and downstream compatibility across the czar ecosystem.

## Version Scheme
- Start at `v1.0` and increment:
  - **Major** (`v2.0`) for output shape changes, new decision logic, or dependencies that alter system behavior.
  - **Minor** (`v1.1`) for new constraints, clarifications, or grounding rules that do not change the expected schema shape.
  - **Patch** (`v1.0.1`) for phrasing tweaks that do not affect intent, outputs, or controls.
- Record the version in the prompt header and include a brief changelog in the file.

## Tracking Requirements
- Update the registry in `prompts/README.md` with the new version and any schema/contract dependencies.
- Update system-level references under `systems/<system>/` to reflect the current prompt version and rationale.
- Capture evaluation impacts in `eval/test-matrix.md` or system-specific evaluation notes when a change affects scoring or coverage.

## Review Gates
- Prompt changes that affect system behavior or output alignment **must undergo architecture review** using `docs/design-review-standard.md` before adoption.
- Material updates should create or update entries in `DECISIONS.md` or the relevant design review record, including rollback considerations.
- Ensure evaluation harnesses and readiness bundles are rerun when changes could shift outputs or acceptance criteria.

## Change Process
1. Draft the update using `prompts/prompt-template.md`, noting the proposed version increment.
2. Describe the change and expected impact in the prompt’s changelog section.
3. Run targeted evaluations or dry-runs as needed; capture results and regressions.
4. Complete required reviews (architecture and human review) and update registries before merging.
5. Communicate downstream (implementation repos and pipelines) about version adoption and effective date.
