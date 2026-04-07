# Governed Prompt Surfaces

## What governed prompt surfaces are
Governed prompt surfaces are repository files that define, template, or include prompt content capable of changing roadmap ordering, implementation behavior, or architecture review outcomes.

In this repository, governed prompt surfaces include:
- roadmap prompt templates,
- implementation prompt templates,
- architecture review prompt templates,
- reusable prompt templates under `prompts/`,
- governance prompt includes under `docs/governance/prompt_includes/`.

## Why the registry exists
`docs/governance/governed_prompt_surfaces.json` is the single canonical machine-readable registry for governed prompt surfaces.

It exists to prevent silent drift where a new prompt/include/template is added but is not visible to governance checking or contract preflight.

## Governance checker linkage
`scripts/check_governance_compliance.py` reads the canonical registry and:
- classifies prompt files by configured path globs,
- applies required governance references/includes per surface,
- fails explicitly when a governed file misses required references,
- ignores non-governed files cleanly.

## Contract preflight linkage
`scripts/run_contract_preflight.py` consults the same registry-backed checker classification to mark registry-matched prompt files as a governed evaluation surface (`governed_prompt_surface`).

This keeps governance checker and preflight visibility on one taxonomy.

## How to add a new governed prompt surface correctly
1. Add/update the prompt/include/template file.
2. Register its path glob and requirements in `docs/governance/governed_prompt_surfaces.json`.
3. Ensure required references/includes exist in the file body.
4. Run:
   - `python scripts/check_governance_compliance.py --file <path>`
   - `pytest tests/test_governed_prompt_surface_sync.py`
5. Do not merge until both governance checker and sync test pass.

## Why unregistered governed surfaces are blocking defects
An unregistered governed prompt file can bypass required governance references and escape preflight visibility.
That is a fail-open drift condition; therefore it is treated as a blocking defect.
