# Parallel PQX Pre-Flight Record Template (2-Slice)

## Run Identity

- Slice A: `__________`
- Slice B: `__________`
- Baseline commit (shared): `__________`
- Reviewer/Operator: `__________`
- Date (UTC): `__________`

## File Scope Evidence

### Slice A files touched

```text
[paste file list]
```

### Slice B files touched

```text
[paste file list]
```

## Overlap Decisions (YES/NO)

Record one answer per category.

- Runtime file overlap present? YES [ ] / NO [ ]
- Shared test file overlap present? YES [ ] / NO [ ]
- Schema/contract overlap present? YES [ ] / NO [ ]
- `contracts/standards-manifest.json` or central registry overlap present? YES [ ] / NO [ ]
- Control-loop policy overlap present? YES [ ] / NO [ ]
- Certification-gate overlap present? YES [ ] / NO [ ]
- Independently mergeable from baseline? YES [ ] / NO [ ]
- Independently reversible after merge? YES [ ] / NO [ ]

## Fail-Closed Rule

- Any unanswered field = **DENY**.
- Any uncertain overlap decision = **DENY**.
- Any missing evidence = **DENY**.
- Any disqualifying overlap = **DENY**.
- No "proceed with caution" state.

## Pre-Flight Decision

- ALLOW [ ]
- DENY [ ]

Decision rationale (required):

```text
[short, explicit reason]
```
