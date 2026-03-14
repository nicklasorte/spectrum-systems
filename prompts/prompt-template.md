# Prompt Template

Use this structure for any new or revised prompt. Replace bracketed guidance with system-specific details and align with the schemas/contracts referenced.

## Prompt Name
State the prompt title and version (e.g., `Comment Resolution Prompt (v1.1)`).

## Purpose
Summarize the objective and the decision or workflow this prompt supports.

## Inputs
- List required inputs with schema or contract references.
- Note any contextual grounding (rules, manifests, run parameters).

## Expected Outputs
- Describe the output shape and required fields.
- Reference the authoritative schemas/contracts and provenance expectations.

## Constraints
- Guardrails, forbidden behaviors, and grounding rules.
- Determinism requirements, formatting, and citation expectations.

## Failure Modes
- Known edge cases, ambiguity triggers, and what to flag for human review.
- Required fallback behavior when inputs are incomplete or invalid.

## Example Usage
- Provide a minimal example invocation and the expected structured output or disposition.
