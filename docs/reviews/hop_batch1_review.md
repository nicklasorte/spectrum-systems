# HOP-BATCH-1 Red Team Review

Reviewer: HOP-BATCH-1 self-review (A10).
Scope: foundation layer only; no autonomous proposer in scope.
Date: 2026-04-25.

## Method

Each finding below was validated by either:
- a failing test that pins the violation (red), and
- the corresponding fix (green) applied in the same PR.

The simulations follow the explicit red-team list:
- malformed artifacts;
- missing evals;
- schema violations;
- eval tampering;
- trace gaps.

## Findings

### F-01 — Evaluator does not chain through the safety scan
**Severity:** block.
**Evidence:** `evaluator.evaluate_candidate` validates the candidate against
the schema but does not invoke `safety_checks.scan_candidate`. A candidate
that hardcodes an answer or leaks an eval_case_id passes evaluation if the
caller forgets to invoke the safety scan.
**Required fix:** add a single admission entrypoint
`hop.admission.admit_candidate(candidate, eval_cases)` that runs validator +
safety scan and returns a combined `(ok, failures)` tuple. The evaluator's
docstring must require admission before evaluation, and integration tests
must exercise the chain.
**Status:** fixed in this PR (`spectrum_systems/modules/hop/admission.py`,
`tests/hop/test_admission.py`).

### F-02 — Eval set has no integrity check at load time
**Severity:** block.
**Evidence:** `evaluator.load_eval_set_from_files` validates each case
against the schema but does not verify the case's recorded `content_hash`
nor cross-check against the `manifest.json` digest. Anyone could swap a
case file under the manifest's nose.
**Required fix:** add `load_eval_set_from_manifest(manifest_path)` that:
1. validates each case against `hop_harness_eval_case`,
2. recomputes the content hash and compares against the case payload,
3. compares the case's content hash against the manifest entry,
4. fails closed on any mismatch.
**Status:** fixed in this PR.

### F-03 — Candidate idempotency depends on caller-provided content hash
**Severity:** warn.
**Evidence:** `experience_store.write_artifact` accepts the caller's
`content_hash` and `artifact_id`. A misbehaving caller could submit a
payload whose recorded hash does not match its content. The store's
duplicate-protection logic would then permit silent shadow data.
**Required fix:** on every write the store recomputes the content hash from
the payload (excluding `content_hash` + `artifact_id`) and refuses if it
disagrees. The same check runs on read.
**Status:** fixed in this PR.

### F-04 — Trace completeness signal can be inflated
**Severity:** warn.
**Evidence:** the evaluator marks a trace `complete = True` when the runner
returns a value without raising. However, an evaluator-internal step
producing a malformed output is captured in `steps[*].note` but the trace
is still flagged complete. The score's `trace_completeness` then
overstates fidelity.
**Required fix:** mark trace `complete = False` whenever the evaluator
records *any* failure_payload for that case. Re-run the score so
`trace_completeness` reflects only fully-valid runs.
**Status:** fixed in this PR.

### F-05 — Safety scan does not detect verbatim transcript memorization via long ids
**Severity:** warn.
**Evidence:** the static scan covers eval_case_id substrings but a future
candidate could memorize a specific transcript's full transcript_id (only
when long enough to be uniquely identifying). The current eval set has
short ids (`t_short`, `t_one_qa`); future longer ids should still trip
detection.
**Required fix:** broaden the scan to also check transcript_id substrings
of length >= 12 characters; document the rationale (short ids would
generate false positives) and add coverage tests.
**Status:** fixed in this PR.

### F-06 — CLI streams the index but `show-frontier` reads every score artifact
**Severity:** info.
**Evidence:** `hop_cli.cmd_show_frontier` calls `_load_score` for every
score record. With thousands of scores this remains memory-bounded only by
the active frontier computation, which keeps a running list of every
projected point.
**Required fix:** acknowledged in this batch as "best-effort streaming";
hard-bounded eviction is deferred to BATCH-2 (`docs/hop/batch2_followups.md`
lists this). For BATCH-1 we note the cap.
**Status:** documented as a deferred limitation; safety unaffected because
HOP-BATCH-1 has no autonomous loop creating arbitrary scores.

### F-07 — Eval cases and outputs share the same JSON Schema draft but lack a
`$schema` cross-check
**Severity:** info.
**Evidence:** every HOP schema declares draft 2020-12, but the loader does
not assert the declaration; a future contributor could weaken a schema by
swapping the dialect.
**Required fix:** the schema loader (`schemas.load_hop_schema`) now refuses
schemas whose `$schema` is not the 2020-12 dialect.
**Status:** fixed in this PR.

### F-08 — `failure_modes_targeted` array can be empty even for adversarial cases
**Severity:** info.
**Evidence:** the schema accepts an empty `failure_modes_targeted`, which
weakens the trace from each adversarial case to its targeted mode.
**Required fix:** require `minItems: 0` is acceptable (already the case)
but enforce in the eval-set generator that every adversarial / failure
case carries at least one targeted mode. Reflected in
`generate_eval_set.py` self-check.
**Status:** fixed in this PR (generator self-check).

## Severity legend

- **block** — fix required before HOP-BATCH-1 is considered complete.
- **warn** — fix required before any candidate beyond the baseline lands.
- **info** — documented limitation deferred or hardened in BATCH-2.

## Coverage matrix

| Red-team scenario | Defense surface | Test |
| --- | --- | --- |
| Malformed candidate | schema + validator | `test_validator.py::test_validator_rejects_schema_violation` |
| Malformed output | evaluator | `test_evaluator.py::test_malformed_output_is_classified` |
| Runtime exception | evaluator | `test_evaluator.py::test_runtime_error_is_caught_and_emits_failure` |
| Empty eval set | evaluator | `test_evaluator.py::test_evaluator_rejects_empty_eval_set` |
| Eval id leakage | safety_checks | `test_safety_checks.py::test_eval_dataset_leakage_is_detected` |
| Hardcoded answer | safety_checks | `test_safety_checks.py::test_hardcoded_answer_is_detected` |
| Schema weakening | safety_checks | `test_safety_checks.py::test_schema_weakening_is_detected` |
| Eval bypass attempt | safety_checks | `test_safety_checks.py::test_eval_bypass_attempt_is_detected` |
| Trace missing | evaluator | `test_evaluator.py::test_each_case_produces_a_trace` |
| Forged content_hash | experience_store | `test_experience_store.py::test_overwrite_with_different_payload_is_rejected` and `test_store_recomputes_content_hash` |
| Tampered manifest | evaluator | `test_evaluator.py::test_manifest_loader_rejects_tampered_case` |
| Missing admission step | admission | `test_admission.py::test_admission_blocks_unsafe_candidate` |
