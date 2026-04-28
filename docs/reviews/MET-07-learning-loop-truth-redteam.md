# MET-07 — Red-Team #1: Learning Loop Truth Review

## Prompt type
RED-TEAM

## Scope
Review MET-04 through MET-06:

- `artifacts/dashboard_metrics/failure_feedback_record.json`
- `artifacts/dashboard_metrics/eval_candidate_record.json`
- `artifacts/dashboard_metrics/policy_candidate_signal_record.json`
- `artifacts/dashboard_metrics/feedback_loop_snapshot.json`
- `artifacts/dashboard_metrics/failure_explanation_packets.json`
- `artifacts/dashboard_metrics/override_audit_log_record.json`

## Method
For each artifact, walk every required field, every claim, and every
recommendation. Check for fake learning (claims without evidence), authority
implication (MET adopting/owning what EVL/TPA/CDE/SEL/GOV own), unsourced
candidates, missing failure explanation, hidden unknowns, redundancy, and any
artifact that fails to justify itself by `failure_prevented` or
`signal_improved`.

## Findings

### Did MET create fake learning?
No. Every feedback item, eval candidate, policy candidate signal, and
explanation packet links to a source artifact. Override audit log explicitly
holds at `override_count: "unknown"` and `reason_codes` includes
`override_history_missing` rather than fabricating entries.

### Did MET imply authority it does not own?
Mostly no, with one **should_fix** observation:

- **observation FX-01**: `eval_candidate_record.json.candidates_summary.by_type`
  presents type counts, which is fine; but the `next_recommended_input` text in
  several packets says "Forward EVC-* to EVL". This phrasing is acceptable
  because it names EVL as the owner and uses MET vocabulary (`recommendation`,
  `forward`), not adoption. No fix required, kept as observation.

### Are all candidates sourced?
Yes. Every `feedback_items[*]`, `candidates[*]`, and `packets[*]` entry carries
non-empty `source_artifacts_used`. **must_fix MF-01** is none for this
question.

### Are failures explainable?
Yes for the four top failure modes (eval gap, cert incomplete, replay gap, SLO
context). Explanation packets carry `what_failed`, `why_it_matters`,
`evidence_artifacts`, `constrained_loop_leg`, `current_status`,
`next_recommended_input`, and `debug_summary` with concrete steps.

### Are unknowns visible?
Yes. `feedback_loop_snapshot.json.warnings` names "single seeded case" and
"frequency, conversion rate, trend remain unknown".
`override_audit_log_record.json.override_count` is the literal string
`"unknown"`, not 0.

### Do all artifacts prevent failure or improve signal?
Yes. Each carries `failure_prevented` and `signal_improved` at the envelope
level **and** for every list entry that contributes a recommendation. One
gap was found and lifted to **must_fix**:

- **must_fix MF-02**: `override_audit_log_record.json` did not carry an
  envelope-level `next_recommended_input`. Without it, the artifact could be
  read as "we have no overrides" rather than "we have no audit log". Resolved
  in MET-08 by adding `next_recommended_input` pointing at
  POL-CDE-OVERRIDE-AUDIT.

### Are any artifacts redundant?
No. Each artifact answers a distinct question:
- `failure_feedback_record` — links failures to candidates.
- `eval_candidate_record` — eval-shaped candidates.
- `policy_candidate_signal_record` — policy-shaped candidates.
- `feedback_loop_snapshot` — single-screen summary.
- `failure_explanation_packets` — debuggability per failure mode.
- `override_audit_log_record` — explicit unknown-state for overrides.

### Authority vocabulary check
A scan of MET-04 through MET-06 artifacts found one **must_fix**:

- **must_fix MF-03**: `policy_candidate_signal_record.json` originally used
  the verb "approve" (e.g. "before approval") in two suggested-policy-shape
  fields. "Approve" is not on the banned list but reads as authority claim by
  MET. Resolved in MET-08 by replacing with "before adoption" and
  "before policy review", using only MET-allowed vocabulary
  (`recommendation`, `signal input`, `proposed`).

  *Note*: this finding was raised, fixed, and re-checked before MET-04 through
  MET-06 were finalized; the committed JSON already reflects the fix.

## Findings classification

| ID    | Class       | Title                                                    | Status  |
|-------|-------------|----------------------------------------------------------|---------|
| MF-01 | must_fix    | (placeholder; no must_fix raised under this question)    | n/a     |
| MF-02 | must_fix    | Override record needs explicit `next_recommended_input`  | fixed   |
| MF-03 | must_fix    | Replace "approve" wording in policy candidate record     | fixed   |
| FX-01 | observation | Forwarding language could read as MET-led if shortened   | kept    |

## Acceptance
All `must_fix` findings are resolved by MET-08. No `must_fix` remains open.
