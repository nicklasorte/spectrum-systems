# Repo Maintenance Checklist

Run this checklist regularly to keep the repository coherent and non-duplicative.

- [ ] README links resolve to existing files and current directories (`systems/`, `schemas/`, `prompts/`, `eval/`, `docs/system-map.md`).
- [ ] `docs/system-status-registry.md` aligns with `docs/system-map.md` and `SYSTEMS.md`.
- [ ] Every system folder contains `overview.md`, `interface.md`, `design.md`, `evaluation.md`, and `prompts.md`.
- [ ] Schema inventory in `schemas/README.md` matches files on disk and version fields.
- [ ] Prompt registry in `prompts/README.md` is current and includes purpose/inputs/outputs/constraints/grounding/version.
- [ ] Evaluation README files cite the schemas and prompts they validate; `eval/test-matrix.md` lists all systems.
- [ ] Provenance and reproducibility standards are referenced from system interfaces.
- [ ] Terminology and naming are consistent with `docs/terminology.md` and `GLOSSARY.md`.
- [ ] No orphaned docs; any deprecated doc points to its canonical replacement.
- [ ] Recent changes are reflected in `CHANGELOG.md` with short, factual entries.
