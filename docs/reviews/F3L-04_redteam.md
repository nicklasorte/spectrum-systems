# F3L-04 Red-Team — Route PRL Eval Candidates Into Governed Regression Intake

Scope: red-team review of the F3L-04 slice. F3L-04 adds a governed
observation-only intake artifact, `prl_eval_regression_intake_record`,
that proves PRL eval candidates produced from CLP/PRL failures have
been routed into a governed regression-coverage intake surface. The
intake record is emitted by `scripts/run_pre_pr_reliability_gate.py`
at the end of every run that persists artifacts to disk and is written
to `outputs/prl/prl_eval_regression_intake_record.json`.

Authority boundary preserved: PRL emits candidate/intake evidence
only. EVL retains canonical authority over eval acceptance, coverage,
and dataset semantics per `docs/architecture/system_registry.md`. The
intake record is observation-only; it does not introduce a new gate,
shift APU's observation-only role, or modify CLP's gate-status
authority.

## Authority-safe vocabulary

This document avoids reserved owner-authority verbs and their negated
forms. PRL emits failure, repair-candidate, eval-candidate, and
intake evidence. APU emits PR-update readiness observations. CLP
emits a pre-PR gate status. EVL retains eval acceptance, coverage,
and dataset semantics. None of these systems claim admission,
execution-closure, policy, continuation, or final-gate signal
authority on behalf of canonical owners.

## Threat scenarios

### 1. Eval candidate prose counted as evidence

Disposition: **closed**.
Mechanism: `prl_eval_regression_intake_record.schema.json` requires
`eval_candidate_refs` to be an array of non-empty path-shaped strings.
When `intake_status=present`, the schema requires
`eval_candidate_refs.minItems >= 1`. PR body prose, comments, or
markdown text cannot satisfy the schema because they would either be
rejected as non-string or produce empty `eval_candidate_refs`. Tests:
`tests/prl/test_eval_regression_intake.py::test_pr_body_prose_cannot_substitute_for_candidate_refs`,
`tests/prl/test_eval_regression_intake.py::test_intake_status_present_requires_candidate_refs`.

### 2. Present intake without `eval_candidate_refs`

Disposition: **closed**.
Mechanism: `allOf` conditional in the schema enforces
`intake_status=present` ⇒ `eval_candidate_refs.minItems >= 1`. The
builder also fails closed: with zero candidates and zero failure
packets it lands on `intake_status=missing` /
`coverage_intent=not_applicable`. There is no public path that yields
`present` without real candidate refs. Tests:
`test_intake_status_present_requires_candidate_refs`,
`test_builder_fails_closed_for_present_without_refs`,
`test_pr_body_prose_cannot_substitute_for_candidate_refs`.

### 3. Intake record lacks source failure refs

Disposition: **closed**.
Mechanism: `source_failure_packet_refs` is a required field. When PRL
processes failure packets, the gate runner appends each packet's
persisted file path to `intake_failure_packet_paths` and feeds the
list into the intake builder. Tests:
`tests/prl/test_pre_pr_gate_persistence.py::test_intake_record_links_back_to_failure_packets_and_index`
asserts every recorded packet ref resolves to a file under
`failure_packets/`.

### 4. Intake record lacks PRL artifact index ref

Disposition: **closed**.
Mechanism: `prl_artifact_index_ref` is required by the schema. The
gate runner computes the index path immediately before building the
intake record and passes it in. Tests:
`test_intake_record_binds_to_artifact_index_and_failure_packets`,
`test_run_gate_writes_eval_regression_intake_record`.

### 5. Unknown failures treated as clean

Disposition: **closed**.
Mechanism: when every candidate is `unknown_failure`, the builder
returns `intake_status=partial` with
`coverage_intent=manual_review_required` and
`reason_codes=[unknown_failure_class_requires_manual_review]`. The
schema's conditional rule requires `partial` to carry at least one
reason code, so a silent "clean" intake claim cannot validate. Test:
`test_unknown_failure_routes_to_manual_review_required`.

### 6. PRL appears to own final eval acceptance

Disposition: **closed**.
Mechanism: the schema pins `authority_scope` to the const
`"observation_only"` and `source_system` to the const `"PRL"`. The
schema description, the bridge module docstring, the gate-runner
docstring, and the standards-manifest entry all repeat that EVL
retains final eval acceptance, coverage, and dataset semantics per
`docs/architecture/system_registry.md`. The intake record carries no
gate authority: it does not redefine `gate_recommendation` and adds no
new precedence for downstream consumers. Tests:
`test_authority_safe_language_preserved`,
`test_schema_pins_authority_scope_to_observation_only`,
`test_schema_rejects_non_prl_source_system`.

### 7. Missing reason_codes for partial / missing / unknown

Disposition: **closed**.
Mechanism: `allOf` conditionals in the schema require
`reason_codes.minItems >= 1` for each of `partial`, `missing`, and
`unknown`. The builder produces deterministic reason codes for every
non-`present` outcome. Tests:
`test_partial_status_requires_reason_codes_in_schema`,
`test_intake_status_unknown_requires_reason_codes_in_schema`,
`test_failures_without_candidates_yield_missing_with_reason_codes`,
`test_clean_run_yields_missing_with_no_failures_reason_code`.

### 8. Candidate refs point to missing files but intake claims present

Disposition: **bounded — known seam, deferred to F3L-05+**.
Mechanism: F3L-04 records the candidate file paths PRL itself just
persisted to disk via `_persist_artifact`, so within a single PRL run
the refs always resolve to real files. A future slice can add an APU
or replay-side check that re-walks
`eval_candidate_refs` and surfaces a
`candidate_ref_missing_on_disk` reason code if a referenced file is
later deleted. The reason-code constant is already defined in
`spectrum_systems/modules/prl/eval_regression_intake.py` so a future
consumer can attach it without a new schema change. F3L-04 does not
broaden APU per scope policy.

### 9. Repeated failures do not produce regression intake evidence

Disposition: **closed**.
Mechanism: every PRL run that processes failure packets also writes
`prl_eval_regression_intake_record.json`. The `evidence_hash` includes
sorted `eval_candidate_refs`, `accepted_candidate_refs`,
`rejected_candidate_refs`, `source_failure_packet_refs`,
`intake_status`, `coverage_intent`, and `reason_codes`, so distinct
failure surfaces produce distinct hashes. Identical inputs produce
identical hashes (deterministic). Tests:
`test_evidence_hash_changes_when_candidate_refs_change`,
`test_evidence_hash_stable_for_identical_inputs`,
`test_intake_record_evidence_hash_changes_when_candidates_change`.

### 10. Authority language regression

Disposition: **closed**.
Mechanism: the schema description and the standards-manifest entry
explicitly state PRL retains classification and eval-candidate
authority only and that EVL retains final eval acceptance. The
schema `authority_scope` field is a `const` (`observation_only`) and
`source_system` is a `const` (`PRL`); both are tested for rejection of
drift values such as `control_signal` or `APU`. Tests:
`test_schema_pins_authority_scope_to_observation_only`,
`test_schema_rejects_non_prl_source_system`,
`test_authority_safe_language_preserved`.

## Out-of-scope (intentionally not addressed)

* No automatic mutation of canonical eval datasets. F3L-04 emits
  intake evidence only; EVL retains acceptance/coverage authority.
* No GitHub workflow changes, dashboard changes, or broad EVL
  refactor.
* APU is **not broadened** to consume the intake record in this slice.
  A future slice can add an APU-side compliance observation that reads
  `outputs/prl/prl_eval_regression_intake_record.json`.

## Summary

The F3L-04 slice closes ten of the ten enumerated red-team scenarios.
Threat scenario 8 is a known seam tracked for a future slice that
broadens APU. Authority shape is preserved end-to-end: PRL produces
observation-only intake evidence, EVL retains canonical eval
acceptance and coverage authority per
`docs/architecture/system_registry.md`.
