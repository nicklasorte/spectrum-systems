# M3L-03 Fix Actions

This file records the disposition of every red-team finding from
`docs/reviews/M3L-03_redteam.md`. M3L-03 is observation-only; all
canonical authority remains with AEX, PQX, EVL, TPA, CDE, SEL, LIN,
REP, and GOV per `docs/architecture/system_registry.md`. The parity
record introduces no new gate, no readiness signal, and no admission,
execution, eval, policy, control, or final-gate authority.

| Finding | Disposition | File(s) changed | Test added/updated | Command run |
|---|---|---|---|---|
| MF-01 missing shard artifacts treated as aligned | resolved | `scripts/build_gate_shard_parity_record.py` (`find_missing_artifact_refs`, `detect_parity` partial branch); `contracts/schemas/gate_shard_parity_record.schema.json` (aligned branch requires `missing_artifact_refs.maxItems=0`) | `test_partial_refs_missing_on_disk` | `python -m pytest tests/test_gate_shard_parity_record.py -q` |
| MF-02 stale shard artifacts treated as current | observation; staleness is owned by APR / CLP. M3L surfaces ref-set diffs only | `scripts/build_gate_shard_parity_record.py` (`detect_parity` `apr_clp_mismatch` branch) | `test_apr_clp_ref_set_mismatch` | `python -m pytest tests/test_gate_shard_parity_record.py -q` |
| MF-03 APR and CLP referencing different artifacts not detected | resolved | `scripts/build_gate_shard_parity_record.py` (`apr_clp_mismatch` rule); schema aligned branch forbids `apr_clp_mismatch=true` | `test_apr_clp_ref_set_mismatch` | `python -m pytest tests/test_gate_shard_parity_record.py -q` |
| MF-04 GitHub shard failure not flagged | resolved | `scripts/build_gate_shard_parity_record.py` (`github_escape`, `clp_github_mismatch`); `classify_github_shard_status` translates summary blocking reasons into `fail` / `missing` / `unknown`; schema aligned branch forbids both flags | `test_apr_pass_github_fail_drift_with_github_escape`, `test_clp_pass_github_fail_drift_with_clp_github_mismatch` | `python -m pytest tests/test_gate_shard_parity_record.py -q` |
| MF-05 unknown treated as aligned | resolved | `detect_parity` early-exits to `unknown` when any input is missing; schema aligned branch requires non-null APR/CLP/summary refs and non-empty shard ref sets | `test_missing_shard_summary_unknown`, `test_missing_apr_unknown`, `test_missing_clp_unknown`, `test_schema_forbids_present_aligned_without_refs` | `python -m pytest tests/test_gate_shard_parity_record.py -q` |
| MF-06 builder recomputes or runs tests | resolved | `scripts/build_gate_shard_parity_record.py` makes no `subprocess` call, no `pytest` import, no shard-runner import; loads JSON only | `test_builder_does_not_invoke_subprocess`, `test_builder_does_not_mutate_inputs` | `python -m pytest tests/test_gate_shard_parity_record.py -q` |
| MF-07 authority wording leak | resolved | schema declares `authority_scope: const observation_only`; reason-code vocabulary uses measurement nouns only; tests grep the record for forbidden authority verbs | `test_record_does_not_carry_authority_verbs_in_reason_codes`, `test_record_has_no_readiness_or_gate_fields` | `python -m pytest tests/test_gate_shard_parity_record.py -q` |
| MF-08 artifact refs missing but not flagged | resolved | every detection branch in `detect_parity` populates the finding's `artifact_refs` (or names the empty-ref case explicitly via the `shard_ref_set_empty_for_at_least_one_system` reason code) | `test_apr_pass_github_fail_drift_with_github_escape` (asserts the GitHub refs are surfaced in the finding) | `python -m pytest tests/test_gate_shard_parity_record.py -q` |
| MF-09 builder secretly emits readiness or gate signals | resolved | schema `additionalProperties: false` forbids any field outside the declared list; declared list contains no `*_ready_*`, no `gate_status`, and no field name that matches any forbidden authority cluster term (canonical owners listed in `contracts/governance/authority_shape_vocabulary.json`) | `test_record_has_no_readiness_or_gate_fields` | `python -m pytest tests/test_gate_shard_parity_record.py -q` |

No `must_fix` finding is left unresolved. M3L-03 ships as a measurement
artifact only.
