# PQX-CLT-017 — Parallel PQX Pre-Flight Checklist (2-Slice)

Use this checklist before starting any 2-slice parallel PQX run.

**Gate:** every check must be answered **YES**.

## Required Inputs

- Slice A identifier: `__________`
- Slice B identifier: `__________`
- Baseline commit (same for both slices): `__________`
- Evidence links/paths for both slices: `__________`

## Eligibility Checks (YES/NO)

Mark one answer per line.

1. No runtime file overlap between Slice A and Slice B. YES [ ] / NO [ ]
2. No shared test file overlap between Slice A and Slice B. YES [ ] / NO [ ]
3. No schema/contract overlap between Slice A and Slice B. YES [ ] / NO [ ]
4. No `contracts/standards-manifest.json` or central registry overlap. YES [ ] / NO [ ]
5. No control-loop policy overlap between Slice A and Slice B. YES [ ] / NO [ ]
6. No certification-gate overlap between Slice A and Slice B. YES [ ] / NO [ ]
7. Slice A and Slice B are independently mergeable from the baseline. YES [ ] / NO [ ]
8. Slice A and Slice B are independently reversible after merge. YES [ ] / NO [ ]

## Fail-Closed Decision Rule

- Any unanswered field = **DENY**.
- Any uncertain overlap decision = **DENY**.
- Any missing evidence = **DENY**.
- Any **NO** answer = **DENY**.
- Only all required fields completed + all checks **YES** = **ALLOW**.

No "proceed with caution" state is permitted.

## Final Pre-Flight Decision

- ALLOW [ ]
- DENY [ ]

Reviewer/Operator: `__________`
Date (UTC): `__________`
