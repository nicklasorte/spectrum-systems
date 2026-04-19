# Postmortem Capture + Exception Governance

Structured incident documentation and exception lifecycle management.

## Postmortem Artifact

Required on every failed run:
- Root causes (schema, policy, eval, drift, human error)
- Actions (immediate, preventive, detective, corrective)
- Timeline of events
- Links to contributing artifacts
- Severity (S0-S4)

Status workflow: open → in_progress → resolved

## Exception Governance

Every exception is an artifact:
- Target artifact ID
- Owner, reason, outcome
- Expiry date (default 30 days)
- Conversion status

Backlog audits track health:
- Total active exceptions
- Overdue exceptions
- Unconverted exceptions

On critical status: FREEZE promotion until backlog addressed.
