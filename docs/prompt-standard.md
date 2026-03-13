# Prompt Standard

All AI workflows must use prompts structured for determinism and traceability. Every prompt must include:
- **role**: the agent persona and responsibilities.
- **context**: relevant background, artifacts, and assumptions.
- **task**: the specific action to perform.
- **constraints**: guardrails, boundaries, and exclusions.
- **verification**: checks, tests, or acceptance criteria to self-audit output.
- **expected output schema**: structured format the model must follow.

Prompts should generate structured outputs whenever possible, aligned to the schemas in this repository and linked to evaluation harnesses.
