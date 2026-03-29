# PQX Slice Continuation (G2 B15–B18)

## Why explicit continuation is required

Single-slice governance proves isolated trust, but sequential execution introduces a new failure class: informal carry-forward. G2 introduces `pqx_slice_continuation_record` as the only governed bridge from slice N to slice N+1, so admission is artifact-authoritative instead of runtime-assumption-authoritative.

## What governs slice-to-slice admission

Slice 2 admission now requires all of the following from slice 1:

1. Canonical `pqx_slice_execution_record` reference
2. Successful done-certification reference
3. Canonical audit bundle reference
4. Valid continuation record binding prior and next step IDs and lineage
5. Continuity state parity between persisted state and reconstructed continuation truth

If any gate fails, continuation is blocked with deterministic block classes:

- `INVALID_SLICE_CONTINUATION`
- `PRIOR_SLICE_NOT_GOVERNED`
- `CONTINUATION_STATE_MISMATCH`

## Why certification and audit are hard prerequisites

Continuation no longer treats execution success as sufficient. A prior slice must be both certified and auditable before the next slice runs. This preserves trust boundaries and prevents bundle state from overriding governed artifact truth.

## Replay parity checks for two-slice governance

`verify_two_slice_replay(...)` compares first-run and replay state for:

- continuation records
- execution history ordering and outcomes
- certification completion status by slice
- audit completion status by slice

Parity produces a governed `prompt_queue_replay_record` with `status=pass`; mismatch fails closed and marks replay verification status as `fail` in both sequence states.
