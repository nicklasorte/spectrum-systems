# Parallel PQX Observability Record Template (2-Slice)

All fields are required unless explicitly marked optional.

## Run Identity

- **Run ID:** `<parallel run identifier>`
- **Timestamp (UTC):** `YYYY-MM-DDThh:mm:ssZ`
- **Slice Pair:** `<slice_a_id> + <slice_b_id>`
- **Window ID (optional):** `<daily|weekly|batch window identifier>`

## Core Outcome Fields

- **Outcome:** `pass | fail`
- **Failure Type (if fail):** `none | slice_local_failure | cross_slice_interference | ambiguous_failure`
- **Containment State:** `not_required | active | recovered | unrecovered`
- **Recovery Status:** `not_applicable | recovered | unrecovered`
- **Certification Path Status:** `unchanged | requires-review | blocked`

## Metric Contribution (Per Run)

- **Counts Toward Parallel Run Count:** `YES` (fixed)
- **Counts Toward Pass/Fail Rate As:** `pass | fail`
- **Counts Toward Slice Local Failure Rate:** `YES | NO`
- **Counts Toward Cross-Slice Interference Rate:** `YES | NO`
- **Counts Toward Ambiguous Failure Rate:** `YES | NO`
- **Counts Toward Rollback Frequency:** `YES | NO`
- **Counts Toward Recovery Success Rate:** `YES | NO | N/A`
- **Counts Toward Certification Path Stability:** `stable | unstable`

## Evidence and Notes

- **Observed Signals:** `<explicit, evidence-based signal summary>`
- **Attribution Clarity:** `clear | unclear`
- **Actions Taken:** `<containment/rollback/review actions>`
- **Operator Notes:** `<freeform notes with concrete evidence references>`

## Fail-Closed Checks (Must Hold)

- If any required signal is unclear, classify run contribution as at least `degraded` in window summary.
- If any required metric contribution field is missing, classify run contribution as at least `degraded`.
- If attribution is `unclear`, failure type must be `ambiguous_failure`.
- If recovery evidence is incomplete, `Recovery Status` must be `unrecovered`.

## Window Signal Classification (for summary rollup)

- **Signal Category:** `stable | degraded | unstable`
- **Threshold Triggered:** `<none | degraded threshold name | unstable threshold name>`
- **Parallel Run Block Required:** `YES | NO`
- **Rationale:** `<concise, evidence-backed rationale>`
