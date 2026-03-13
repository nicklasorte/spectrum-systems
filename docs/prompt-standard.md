# Prompt Standard

All AI workflows must use prompts structured for determinism and traceability.

## Required Prompt Structure
- **role**: Agent persona, authorities, and boundaries.
- **context**: Relevant artifacts, assumptions, and prior decisions needed to ground the response.
- **task**: Specific action to perform, tied to the current artifact chain stage.
- **constraints**: Guardrails, exclusions, and policy or engineering limits.
- **verification**: Self-checks, acceptance criteria, or tests the model must apply before responding.
- **expected output schema**: Explicit schema or contract the response must satisfy.

## Structured Output Guidance
- Default to structured outputs (JSON, YAML, tables) bound to repository schemas (`comment-schema`, `issue-schema`, `study-output-schema`, etc.).
- Reference evaluation harness expectations (see `eval/*`) to define verification steps.
- Require deterministic parameters (fixed temperature, ordered steps) for repeatable results.
- Embed provenance fields whenever the output will flow into downstream systems.
