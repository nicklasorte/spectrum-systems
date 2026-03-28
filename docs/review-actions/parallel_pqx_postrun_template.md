# Parallel PQX Post-Run Record Template (2-Slice)

> Complete every field. Any blank, ambiguous, or unsupported entry results in **FAIL**.

## Run metadata
- Run ID:
- Date (UTC):
- Operator:

## Slice identification
- Slice A:
- Slice B:

## File touch sets
- Files touched by Slice A:
- Files touched by Slice B:
- File overlap result (select one): `none` | `overlap`

## Merge order
- Merge order (select one): `A→B` | `B→A`

## Behavior evidence
- BEFORE behavior (Slice A):
- BEFORE behavior (Slice B):
- AFTER behavior (Slice B):
- BEFORE vs AFTER comparison for Slice B (select one): `equivalent` | `not-equivalent` | `ambiguous`
- Comparison evidence reference(s):

## Isolation and attribution checks
- Semantic overlap result (select one): `none` | `overlap`
- Shared assumption result (select one): `none` | `present`
- Attribution clarity (select one): `clear` | `unclear`
- Attribution rationale (required):

## Promotion/certification path
- Status (select one): `unchanged` | `requires-review` | `blocked`
- Notes:

## Final outcome
- Final outcome (select one): `pass` | `fail`
- Outcome rationale:

## Fail-closed gate (must be YES to pass)
- All required fields completed with evidence? `yes` | `no`
- Any unclear attribution? `yes` | `no`
- Any ambiguous behavior comparison? `yes` | `no`
- Any soft conclusion (e.g., “looks okay”)? `yes` | `no`

**Enforcement:**
- If any answer above is missing, set Final outcome = `fail`.
- If “Any unclear attribution?” = `yes`, set Final outcome = `fail`.
- If “Any ambiguous behavior comparison?” = `yes`, set Final outcome = `fail`.
- If “Any soft conclusion?” = `yes`, set Final outcome = `fail`.
