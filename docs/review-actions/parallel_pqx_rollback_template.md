# Parallel PQX Rollback + Containment Template (2-Slice)

All fields are required. Do not omit or rename fields.

## Rollback + Containment Record

- **Run ID:** `<parallel run identifier>`
- **Event Timestamp (UTC):** `YYYY-MM-DDThh:mm:ssZ`
- **Slice(s) Affected:** `A | B | A+B`
- **Failure Type:** `slice_local_failure | cross_slice_interference | ambiguous_failure`
- **Containment State:** `recovered | unrecovered`
- **Attribution Clarity:** `clear | unclear`

## Required Evidence

- **Baseline Commit:** `<sha>`
- **Merge Order:** `A→B | B→A`
- **Validation State (Before Failure):** `<explicit checks + outcomes>`
- **Validation State (After Rollback/Containment):** `<explicit checks + outcomes>`
- **Attribution Evidence:** `<why attribution is clear or unclear>`

## Decision and Action

- **Rollback Action Taken:** `<exact rollback action(s)>`
- **Containment Action Taken:** `<stop/hold/isolate actions taken>`
- **Serial Fallback Required:** `YES | NO`
- **Recovery Confirmed:** `YES | NO`
- **Final Outcome:** `recovered | unrecovered`

## Fail-Closed Assertions (Must Hold)

- If attribution is `unclear`, then **Failure Type must be `ambiguous_failure`**.
- If recovery evidence is incomplete or uncertain, **Recovery Confirmed must be `NO`**.
- If Recovery Confirmed is `NO`, **Final Outcome must be `unrecovered`**.
- “Probably recovered” or equivalent soft conclusions are prohibited.

## Rationale

- **Rationale:** `<concise, evidence-based explanation for classification, rollback scope, containment status, and serial fallback decision>`
