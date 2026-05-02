# F3L-01 Red-Team — Require PRL Evidence Before APU PR-Update Readiness After CLP Block

Scope: red-team review of the F3L-01 slice. F3L-01 wires PRL
failure-normalization evidence into the APU PR-update readiness guard so
that, when CLP reports the blocking gate status on a repo-mutating slice,
APU emits `not_ready` unless artifact-backed PRL evidence is supplied.

Authority boundary preserved: APU remains observation-only. PRL retains
all classification, repair-candidate, and eval-candidate authority. CLP
retains gate-status authority. Canonical authority remains with the
systems declared in `docs/architecture/system_registry.md`.

## Authority-safe vocabulary

This document avoids reserved owner-authority verbs and their negated
forms. APU emits PR-update readiness observations. PRL emits failure,
repair-candidate, and eval-candidate evidence. CLP emits a pre-PR gate
status. None of these systems claim admission, execution-closure,
eval, policy, continuation, or final-gate signal authority on behalf of
canonical owners.

## Threat scenarios

### 1. CLP block treated as PR-update ready without PRL evidence

Disposition: **closed by F3L-01**.
Mechanism: `evaluate_pr_update_ready` now consults `prl_result` against
the `repo_mutating_clp_block_requires_prl_evidence` rule. With PRL
evidence absent and CLP gate status blocking, the evaluation appends
`prl_evidence_missing_for_clp_block` to `reason_codes` and surfaces a
`required_follow_up` entry pointing to PRL. Test:
`test_clp_block_with_no_prl_evidence_yields_not_ready`.

### 2. Missing PRL evidence counted present

Disposition: **closed**.
Mechanism: when `prl_result` is `None`, `_evaluate_prl_evidence` returns
`status=missing` with a `prl_evidence_missing` reason code, and APU
emits `prl_evidence_status="missing"` in the output artifact.
`prl_evidence_status="present"` requires `prl_result_ref` to be a
non-empty string by schema invariant. Test:
`test_prl_present_status_requires_prl_result_ref_in_artifact` exercises
the invariant via schema validation.

### 3. PRL evidence exists but lacks failure packet refs

Disposition: **closed**.
Mechanism: `_evaluate_prl_evidence` adds
`prl_failure_packets_missing_for_clp_block` to `blocking_reasons` when
the PRL artifact reports `failure_classes` but no
`failure_packet_refs`, regardless of `gate_recommendation`. Test:
`test_clp_block_with_prl_evidence_missing_failure_packet_refs_blocks`.

### 4. PRL evidence exists but lacks repair/eval candidate refs

Disposition: **closed**.
Mechanism: when an observed failure class is in
`prl_known_repairable_failure_classes`, the evaluator surfaces
`prl_repair_candidates_missing_for_repairable_failure` and
`prl_eval_candidates_missing_for_repairable_failure` reason codes.
Test:
`test_clp_block_with_prl_evidence_missing_repair_and_eval_candidates_blocks`.

### 5. Unknown PRL failure treated as clean

Disposition: **closed**.
Mechanism: `prl_unknown_failure_classes` includes `unknown_failure`. An
observation of an unknown class causes
`prl_unknown_failure_class_observed` to be added to `reason_codes` and
sets `human_review_required=True`, yielding readiness status
`human_review_required` per current policy. Test:
`test_clp_block_with_prl_unknown_failure_yields_human_review`.

### 6. PR body prose counted as evidence

Disposition: **closed**.
Mechanism: `load_prl_result` accepts only JSON files whose
`artifact_type == "prl_gate_result"`. A prose JSON payload (or any
non-conforming envelope) is rejected and returns `None`; APU then
treats it as missing. Test: `test_pr_body_prose_is_not_prl_evidence`.

### 7. CLP warn treated as clean without policy support

Disposition: **closed (existing rule preserved)**.
Mechanism: F3L-01 does not change CLP-warn handling. The existing
`clp_warn_requires_explicit_allow` rule continues to require every
warning reason code to appear in
`policy.allowed_warning_reason_codes`; a warn with an unallowed reason
code yields `not_ready`. F3L-01 does not require PRL evidence on CLP
warn so that the warn path remains governed by the existing TPA-owned
policy. Test:
`test_clp_warn_policy_allowed_does_not_require_prl_evidence` and
existing `test_clp_warn_unallowed_reason_blocks`.

### 8. repo_mutating unknown treated as safe

Disposition: **closed (existing rule preserved)**.
Mechanism: `repo_mutating_unknown_yields_not_ready` already adds
`repo_mutating_unknown` to `reason_codes` when the value is None.
F3L-01's PRL leg gates on `repo_mut_value` so it does not need to
re-implement the unknown-yields-not-ready rule. Test:
`test_repo_mutating_unknown_yields_not_ready`.

### 9. APU claims authority instead of readiness observation

Disposition: **closed**.
Mechanism: APU policy preserves
`authority_scope_must_be_observation_only`. The APU artifact's
`authority_scope` is constrained to `observation_only` by the schema
const. The build helper sets it explicitly. The new PRL fields are
observation refs and do not change APU authority. Test:
`test_apu_artifact_authority_scope_observation_only` (existing) and
`test_prl_artifact_negated_authority_phrases_absent` (new).

### 10. Reserved owner-vocabulary in non-owner files

Disposition: **closed**.
Mechanism: F3L-01 review/review-action docs use neutral readiness
language. The APU artifact tests scan the JSON blob and the
PR-evidence section markdown for the canonical-owner-vocabulary
tokens listed in the APU test fixture as quoted strings (those tokens
are owned by GOV/CDE/SEL/REL per
`docs/architecture/system_registry.md`) and for their negated forms.
Tests: `test_apu_artifact_does_not_claim_owner_authority` and
`test_prl_artifact_negated_authority_phrases_absent`.

### 11. PRL repair-attempt count bypasses current policy

Disposition: **out of scope but observed**.
Mechanism: APU policy preserves `max_repair_attempts: 0` — APU never
applies repairs. The PRL repair-candidate-count surfaced in the APU
artifact is observation only. Repair authority remains with PRL/CDE
per the canonical owner table. F3L-01 does not introduce a repair-loop
trigger and does not override `must_not_do.auto_apply_repairs`.

### 12. Repeated failures do not create/propose eval regression coverage

Disposition: **closed by reflection of PRL evidence**.
Mechanism: APU now requires that, for known repairable failure
classes, PRL evidence include eval candidate refs
(`prl_eval_candidates_missing_for_repairable_failure`). PRL retains
authority over the eval-case-candidate generation flow; APU only
records the evidence ref as a readiness observation.

## Residual risks

- A PRL artifact whose JSON envelope is internally inconsistent (e.g.
  declares a `failure_classes` entry but the corresponding
  `failure_packet_refs` are placeholders) is detected only at the
  ref-presence layer. Deeper PRL artifact integrity remains PRL's
  authority (and would be caught by PRL's own schema validation when
  the artifact is produced).
- APU does not validate the PRL schema itself when consuming the
  artifact. The expected `artifact_type` and structural shape are
  guarded by the APU loader. Fail-closed defaults apply.
- A future PRL gate vocabulary extension (new `gate_recommendation`
  value) would surface as an unrecognized non-blocking value. The
  policy's `prl_blocking_gate_recommendations` list is the seam for
  forward-compatibility; new values can be admitted via a TPA-owned
  policy update.

## Summary

All threat scenarios listed in the F3L-01 task brief are addressed by
fail-closed checks in `_evaluate_prl_evidence` and the APU policy. APU
remains observation-only and does not redefine PRL, CLP, AEX, PQX, EVL,
TPA, CDE, SEL, LIN, REP, or GOV authority. No reserved authority verbs
appear in changed non-owner files (this document, the fix-actions doc,
the policy notes, the runtime module, the CLI, the schema, the example,
or the tests).
