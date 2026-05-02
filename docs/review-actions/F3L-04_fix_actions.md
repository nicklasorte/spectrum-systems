# F3L-04 Fix Actions — Promote PRL Eval Candidates Into Governed Regression Coverage Inputs

Each entry below records a must_fix finding from the F3L-04 red-team
review (`docs/reviews/F3L-04_redteam.md`), the file changed to address
it, the test that proves the fix, the validation command run, and the
disposition.

| Finding ID | File changed | Test added/updated | Command run | Disposition |
| --- | --- | --- | --- | --- |
| F3L-04-RT-01 (Eval candidate prose counted as evidence) | `contracts/schemas/prl_eval_regression_intake_record.schema.json` | `tests/prl/test_eval_regression_intake.py::test_pr_body_prose_cannot_substitute_for_candidate_refs`, `::test_intake_status_present_requires_candidate_refs` | `python -m pytest tests/prl/test_eval_regression_intake.py -q` | Closed |
| F3L-04-RT-02 (Present intake without `eval_candidate_refs`) | `contracts/schemas/prl_eval_regression_intake_record.schema.json`, `spectrum_systems/modules/prl/eval_regression_intake.py` | `tests/prl/test_eval_regression_intake.py::test_intake_status_present_requires_candidate_refs`, `::test_builder_fails_closed_for_present_without_refs` | `python -m pytest tests/prl/test_eval_regression_intake.py -q` | Closed |
| F3L-04-RT-03 (Intake record lacks source failure refs) | `spectrum_systems/modules/prl/eval_regression_intake.py`, `scripts/run_pre_pr_reliability_gate.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_intake_record_links_back_to_failure_packets_and_index` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |
| F3L-04-RT-04 (Intake record lacks PRL artifact index ref) | `contracts/schemas/prl_eval_regression_intake_record.schema.json`, `scripts/run_pre_pr_reliability_gate.py` | `tests/prl/test_eval_regression_intake.py::test_intake_record_binds_to_artifact_index_and_failure_packets`, `tests/prl/test_pre_pr_gate_persistence.py::test_run_gate_writes_eval_regression_intake_record` | `python -m pytest tests/prl/test_eval_regression_intake.py tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |
| F3L-04-RT-05 (Unknown failures treated as clean) | `spectrum_systems/modules/prl/eval_regression_intake.py` | `tests/prl/test_eval_regression_intake.py::test_unknown_failure_routes_to_manual_review_required` | `python -m pytest tests/prl/test_eval_regression_intake.py -q` | Closed |
| F3L-04-RT-06 (PRL appears to own final eval acceptance) | `contracts/schemas/prl_eval_regression_intake_record.schema.json`, `contracts/standards-manifest.json`, `spectrum_systems/modules/prl/eval_regression_intake.py`, `scripts/run_pre_pr_reliability_gate.py` | `tests/prl/test_eval_regression_intake.py::test_authority_safe_language_preserved`, `::test_schema_pins_authority_scope_to_observation_only`, `::test_schema_rejects_non_prl_source_system` | `python -m pytest tests/prl/test_eval_regression_intake.py -q` | Closed |
| F3L-04-RT-07 (Missing reason_codes for partial / missing / unknown) | `contracts/schemas/prl_eval_regression_intake_record.schema.json`, `spectrum_systems/modules/prl/eval_regression_intake.py` | `tests/prl/test_eval_regression_intake.py::test_partial_status_requires_reason_codes_in_schema`, `::test_intake_status_unknown_requires_reason_codes_in_schema`, `::test_failures_without_candidates_yield_missing_with_reason_codes`, `::test_clean_run_yields_missing_with_no_failures_reason_code` | `python -m pytest tests/prl/test_eval_regression_intake.py -q` | Closed |
| F3L-04-RT-08 (Candidate refs point to missing files but intake claims present) | `spectrum_systems/modules/prl/eval_regression_intake.py` (reason-code constant `candidate_ref_missing_on_disk` defined for downstream consumers) | n/a — bounded seam, not exercised in F3L-04 (APU not broadened per scope) | n/a | Bounded — deferred to F3L-05+ |
| F3L-04-RT-09 (Repeated failures do not produce regression intake evidence) | `scripts/run_pre_pr_reliability_gate.py`, `spectrum_systems/modules/prl/eval_regression_intake.py` | `tests/prl/test_eval_regression_intake.py::test_evidence_hash_changes_when_candidate_refs_change`, `::test_evidence_hash_stable_for_identical_inputs`, `tests/prl/test_pre_pr_gate_persistence.py::test_intake_record_evidence_hash_changes_when_candidates_change` | `python -m pytest tests/prl/ -q` | Closed |
| F3L-04-RT-10 (Authority language regression) | `contracts/schemas/prl_eval_regression_intake_record.schema.json`, `contracts/standards-manifest.json`, `spectrum_systems/modules/prl/eval_regression_intake.py` | `tests/prl/test_eval_regression_intake.py::test_authority_safe_language_preserved`, `::test_schema_pins_authority_scope_to_observation_only`, `::test_schema_rejects_non_prl_source_system` | `python -m pytest tests/prl/test_eval_regression_intake.py -q` | Closed |

## Test summary

```
python -m pytest tests/prl/test_eval_generator.py tests/prl/test_pre_pr_gate_persistence.py tests/prl/test_eval_regression_intake.py tests/test_prl_auto_invoker.py tests/test_check_agent_pr_update_ready.py -q
```

Result: 112 passed (18 new F3L-04 intake builder cases + 4 new F3L-04
gate-runner persistence cases + existing F3L-01/F3L-02/F3L-03 PRL,
APU, and auto-invoker suites).

## Authority boundary check

PRL emits classification, repair-candidate, eval-candidate, and intake
evidence only. The intake artifact carries `authority_scope =
observation_only` and `source_system = PRL` as schema constants. EVL
retains canonical authority over eval acceptance, coverage, and
dataset semantics per `docs/architecture/system_registry.md`. CLP
gate-status authority and APU's observation-only role are unchanged.
F3L-04 does not redefine PRL, CLP, AEX, PQX, EVL, TPA, CDE, SEL, LIN,
REP, or GOV authority.

## Unresolved must_fix findings

None. F3L-04-RT-08 is a bounded seam with the reason-code already
declared so a future slice can attach it without a schema change.
