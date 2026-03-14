# Spectrum Program Advisor — Prompts (SYS-005)

Prompts should reinforce deterministic, schema-first outputs. Keep prose templated and derived from validated JSON.

## Prompting Principles
- Request contract-valid JSON first; emit Markdown summaries only after JSON passes validation.
- Explicitly state the canonical risk categories and require a category for each risk.
- Instruct models to keep identifiers stable (decision IDs, risk IDs, milestone IDs, assumption IDs).
- Require traceability fields (`source_artifacts`, `source_reference`) for every generated summary element.
- Emphasize decision readiness as the primary score; ask models to justify readiness with blockers and evidence.

## Output Templates
- Program Brief: summarize `decision_readiness`, top risks, open decisions, next best actions, and missing artifacts. Keep sections aligned to contract fields.
- Study Readiness Assessment: list gates with status, missing evidence, dependency risks, and readiness score.
- Next Best Action Memo: list actions with priority, owner, due date, dependencies, and expected impact.

## Guardrails
- Reject new identifiers not present in inputs; prompt models to reuse provided IDs.
- For any low-confidence text, instruct the model to add a `notes` field rather than inventing rationale.
- Keep tone factual and program-management-oriented; avoid speculative language.
