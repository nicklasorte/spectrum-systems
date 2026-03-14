# Evaluation Datasets Framework

Governance guide for evaluation datasets that exercise text-producing engines (prompted models, templating pipelines, and rule-based generators). The goal is to create deterministic, repeatable checks that catch regressions whenever prompts, models, or post-processing logic change.

## Purpose
- Provide shared, versioned datasets that cover happy-path, edge, and adversarial cases for text generation tasks governed by this repo.
- Enable regression testing across prompt updates, model swaps, and scoring rule adjustments before changes are promoted.
- Keep evaluation assets lightweight and schema-aligned so downstream engines can run them without pulling protected data.

## Directory layout
- `evals/fixtures/` — example input cases and prompts the engines should process.
- `evals/rubrics/` — evaluation criteria and scoring guidance for the corresponding fixtures.
- `evals/` (this file) — usage guidance and expectations for maintaining datasets.

## Building a dataset
1. Define scope: what behavior is being exercised (e.g., summarization fidelity, instruction compliance, disposition consistency).
2. Collect fixtures: include nominal, edge, malformed, and regression cases. Document the intended behavior for each case and link to the applicable schema or contract where relevant.
3. Author rubrics: specify blocking vs. warning criteria, acceptable thresholds, and scoring instructions (numeric or categorical) tied to the fixture goals.
4. Version everything: annotate fixture and rubric files with version identifiers so runs can be reproduced when prompts, rules, or models evolve.

## Running evaluations (engines)
1. Pin configuration: capture prompt/rule versions, model ID, temperature/seed, and post-processing steps.
2. Execute all fixtures: run the engine against every case in `evals/fixtures/` and emit outputs aligned to the governed schemas/contracts.
3. Score with rubrics: apply the criteria in `evals/rubrics/` (automated scoring where possible; human review where judgment is required).
4. Record run metadata: produce a run manifest noting dataset version, rubric version, engine configuration, start/end time, and evaluator identity.
5. Compare to baseline: treat rubric failures marked “blocking” as release blockers; investigate deltas for “warning” items.

## Regression expectations
- Run the full evaluation set before major changes: prompt/rule edits, model version changes, post-processor adjustments, or scoring logic changes.
- Add new regression fixtures whenever an escaped defect is discovered; keep them minimal and anonymized.
- Do not overwrite or delete fixtures that guard historical regressions; supersede with new versions when needed and note the rationale.

## Maintenance notes
- Keep fixtures synthetic or sanitized; no operational data lives in this repo.
- Reference governed schemas and contracts instead of redefining output shapes.
- Align updates here with the broader evaluation registry in `eval/` (e.g., `eval/test-matrix.md`) so coverage stays coherent across systems.

## Pointers
- Example fixtures live in `evals/fixtures/`.
- Example rubrics live in `evals/rubrics/`.
- Engines should link their run manifests back to the dataset and rubric versions recorded in this directory.
