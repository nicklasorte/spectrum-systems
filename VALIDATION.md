# Validation

## Purpose
Defines how systems designed in this repository should be evaluated before being trusted for operational use.

## Validation Levels
- **Draft Validation**: Output is suitable for exploration but requires manual verification.
- **Review Validation**: Output has been reviewed by a human expert.
- **Approved Validation**: Output meets reliability standards and can be reused downstream.

## Evaluation Categories
- **Correctness**: Does the output reflect the source data accurately?
- **Traceability**: Can the artifact be traced to its sources?
- **Reproducibility**: Can the same workflow produce the same output?
- **Clarity**: Is the artifact understandable by engineers?
- **Contract Compliance**: Do user-facing artifacts (e.g., the comment resolution matrix spreadsheet) match the exact headers, order, and required/optional fields defined in their governing contract, with no extra visible columns?

All systems should define validation methods before implementation.
