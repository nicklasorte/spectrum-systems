# HOP-BATCH-2 Red Team Review

Reviewer: HOP-BATCH-2 self-review (A18).
Scope: bounded proposer, mutation policy, causal artifacts, trace-diff,
hardened frontier, concurrent experience store, optimization loop.
Date: 2026-04-25.

## Method

Each finding is paired with:

- a failing test that pins the violation (red);
- the corresponding fix (green) applied in the same PR.

Attack surface considered:

1. eval gaming (overfit to eval set);
2. leakage (eval cases inferred or memorized);
3. mutation escape (proposer bypasses policy);
4. schema drift (candidate weakens contracts);
5. frontier bias (bad candidates dominate frontier);
6. trace falsification (traces appear valid but hide errors);
7. concurrency abuse (interleaved writes corrupt the index);
8. promotion creep (HOP self-promoting beyond advisory).

## Findings

### F-09 — Proposer could write to the experience store directly
**Severity:** block.
**Threat:** if `proposer.propose_candidates` were given the live store
handle it could (intentionally or by author error) call
`store.write_artifact` and leak past the optimization loop's
mutation-policy gate.
**Required fix:** the proposer signature accepts only a
`ProposerContext` snapshot — never a live `ExperienceStore`. The
optimization loop is the sole writer.
**Status:** fixed. `proposer.propose_candidates` typing rejects
`ExperienceStore` inputs. Test:
`tests/hop/test_proposer.py::test_proposer_never_receives_live_store`.

### F-10 — Mutation policy could be skipped if a caller invoked admission directly
**Severity:** block.
**Threat:** the admission gate (validator + safety scan) does NOT
enforce mutation policy. A caller could hand a hand-rolled candidate
straight to admission and skip every BATCH-2 check.
**Required fix:** the only legitimate path for a non-baseline candidate
is `optimization_loop.run_proposer_cycle`, which always runs the
mutation policy *before* admission. Documented + enforced by the
integration test
`tests/hop/test_optimization_loop.py::test_pipeline_is_strictly_ordered`.
The mutation policy itself rejects any candidate whose declared
`modified_paths` are outside the candidate's own module file.
**Status:** fixed.

### F-11 — Mutation policy text scan can miss obfuscated patterns
**Severity:** block.
**Threat:** a textual `in source` match (BATCH-1's safety_checks shape)
can be evaded by string concatenation, comments, or `getattr` lookups.
**Required fix:** mutation policy uses an AST scan that detects:
forbidden imports (urllib, requests, subprocess, socket, ctypes,
HOP-internal modules); forbidden calls (`eval`, `exec`, `compile`,
`__import__`, `open`, `globals`, `os.system`, `os.popen`, `subprocess.*`,
`socket.*`); attribute access into the experience store; and reads of
`os.environ` / `sys.argv`.
**Status:** fixed. Test:
`tests/hop/test_mutation_policy.py::test_obfuscated_import_is_caught`.

### F-12 — Required FAQ output fields can be removed in candidate code
**Severity:** block.
**Threat:** a candidate may emit a FAQ payload that omits required
fields (`items`, `transcript_id`, `candidate_id`). The evaluator's
schema check would still catch this, but the policy should also
reject candidates that *structurally* attempt the removal so the
proposer's quota is not wasted.
**Required fix:** mutation policy refuses any source that contains
`del payload.<required>`, `payload.pop("<required>")`, or
`del var["<required>"]` for the required fields.
**Status:** fixed. Test:
`tests/hop/test_mutation_policy.py::test_field_removal_is_rejected`.

### F-13 — Frontier could accept score artifacts with NaN / out-of-range values
**Severity:** block.
**Threat:** an adversarial candidate could emit a score whose
`trace_completeness=NaN` or `cost=-1`. NaN comparisons short-circuit
Pareto checks and would silently dominate every other point.
**Required fix:** `frontier._validate_member_payload` drops scores with
non-finite or out-of-bound objectives. Dropped scores are surfaced via
`FrontierResult.invalid_count` and (in the optimization loop /
CLI) emit `frontier_invalid_member` failure hypotheses.
**Status:** fixed. Test:
`tests/hop/test_frontier_streaming.py::test_nan_score_is_dropped`.

### F-14 — Frontier loaded every score artifact into memory
**Severity:** warn (carry-over from BATCH-1 F-06).
**Threat:** large stores (~10⁵ scores) blew the RSS budget.
**Required fix:** `compute_frontier_streaming` performs a chunked
Pareto merge bounded by `--max-frontier-window`. Each chunk's local
frontier merges with the running global frontier; non-frontier points
are released as soon as their chunk closes.
**Status:** fixed. Test:
`tests/hop/test_frontier_streaming.py::test_streaming_matches_in_memory`.

### F-15 — Concurrent writers could interleave bytes in `index.jsonl`
**Severity:** block.
**Threat:** two evaluator processes appending simultaneously could
produce a half-line in the index, breaking every subsequent
`iter_index` call.
**Required fix:** every `write_artifact` acquires an exclusive
`fcntl.flock` on `index.jsonl.lock` for the full
admit/write/index sequence; artifact files are written via tempfile +
`os.replace`. Lock acquisition fails-closed after a 10s timeout via
`HopStoreError("hop_store_lock_timeout")`.
**Status:** fixed. Test:
`tests/hop/test_experience_store_concurrency.py::test_parallel_writes_serialize_under_lock`.

### F-16 — Trace can be `complete=True` while output is hash-mismatched
**Severity:** warn.
**Threat:** a candidate could fabricate an output whose content_hash
does not match the trace's `output_hash`, hiding a malformed
intermediate.
**Required fix:** the existing evaluator computes `output_hash` from
the *runner output* directly, so the candidate cannot supply a forged
hash. Trace-diff additionally surfaces output-hash mismatches via
the `case_diffs[*].candidate_output_hash` column. Integration test
covers a runner that returns one payload and reports a different hash.
**Status:** fixed by evaluator construction; trace-diff exposes the
signal. Test:
`tests/hop/test_trace_diff.py::test_diff_surfaces_output_hash_mismatch`.

### F-17 — Failure hypothesis could carry free-form claims
**Severity:** warn.
**Threat:** an analyzer that returned a free-form natural language
suspected_cause would let an LLM-driven proposer slip narrative
content through the schema.
**Required fix:** `failure_analysis._suspected_cause` only emits a
small set of structurally-derived labels
(`shared_regression`, `shared_improvement`,
`isolated_regression`, `isolated_improvement`,
`conflicting_signals_present`, `no_observable_per_case_movement`,
`unattributed_<observed>`). The schema constrains
`suspected_cause` to `maxLength=1024`; in practice the strings are
under 64 characters.
**Status:** fixed. Test:
`tests/hop/test_failure_analysis.py::test_suspected_cause_is_enum_like`.

### F-18 — Proposer could exceed its quota and starve the loop
**Severity:** warn.
**Threat:** a misbehaving driver (or a future LLM proposer) could ask
for 10⁶ proposals and exhaust the eval set, the store, and the
frontier window.
**Required fix:** `propose_candidates` raises
`ProposerQuotaExceeded` when `max_proposals` exceeds the registered
template count. The optimization loop's quota check is mirrored at
the proposer boundary so any caller is bounded.
**Status:** fixed. Test:
`tests/hop/test_proposer.py::test_quota_is_enforced`.

### F-19 — Causal hypothesis could be authored without a baseline
**Severity:** warn.
**Threat:** an analyzer that authored a hypothesis without a baseline
score implicitly invented evidence ("this candidate regressed against
nothing").
**Required fix:** `optimization_loop.run_proposer_cycle` skips
hypothesis generation when `baseline_score is None`; the analyzer
itself raises `FailureAnalysisError` if the trace_diff does not match
the supplied candidate ids. Test:
`tests/hop/test_failure_analysis.py::test_mismatched_baseline_is_rejected`.

### F-20 — Trace-diff could compare across eval-set versions
**Severity:** block.
**Threat:** comparing scores from different eval-set versions silently
produces nonsense deltas.
**Required fix:** `trace_diff.compute_trace_diff` raises
`TraceDiffError` when `eval_set_id` or `eval_set_version` mismatch.
**Status:** fixed. Test:
`tests/hop/test_trace_diff.py::test_diff_rejects_eval_set_mismatch`.

### F-21 — Frontier promotion creep
**Severity:** info.
**Threat:** "frontier membership" could be misread as "promote me".
**Required fix:** documentation in `__init__.py` and this review state
explicitly that frontier membership is advisory; promotion still
requires a passing `done_certification_record` per the project
CLAUDE.md governance rules.
**Status:** documented. No code path in HOP marks a candidate
"promotion-ready"; the failure hypothesis emitted by
`failure_analysis` only sets `blocks_promotion=true` for severities
≥ `reject`.

### F-22 — Long mutation-policy AST scan could DoS the loop
**Severity:** info.
**Threat:** a multi-megabyte candidate source could slow every cycle.
**Required fix:** the proposer's deterministic templates produce
candidate sources bounded by the baseline source size + ~200 chars.
Future external proposers should be capped at the validator boundary;
documented as a BATCH-3 followup in `docs/hop/batch3_followups.md`.

## Severity legend

- **block** — fix required before HOP-BATCH-2 is considered complete.
- **warn** — fix required before any non-baseline candidate is
  evaluated against the live store.
- **info** — documented limitation deferred or hardened in BATCH-3.

## Coverage matrix

| Red-team scenario | Defense surface | Test |
| --- | --- | --- |
| Proposer writes to store | proposer + optimization_loop | `test_proposer.py::test_proposer_never_receives_live_store` |
| Proposer skips mutation policy | optimization_loop | `test_optimization_loop.py::test_pipeline_is_strictly_ordered` |
| Forbidden import | mutation_policy | `test_mutation_policy.py::test_forbidden_import_is_rejected` |
| Forbidden call (`eval`, `subprocess.run`) | mutation_policy | `test_mutation_policy.py::test_forbidden_call_is_rejected` |
| Cross-module write | mutation_policy | `test_mutation_policy.py::test_modified_path_outside_candidate_is_rejected` |
| Required field removal | mutation_policy | `test_mutation_policy.py::test_field_removal_is_rejected` |
| Hidden state read (`os.environ`) | mutation_policy | `test_mutation_policy.py::test_env_access_is_rejected` |
| Schema drift (eval/schema dir reference) | mutation_policy + safety_checks | `test_mutation_policy.py::test_eval_dir_literal_is_rejected` |
| NaN / OOB frontier point | frontier | `test_frontier_streaming.py::test_nan_score_is_dropped` |
| Frontier exceeds memory budget | frontier | `test_frontier_streaming.py::test_streaming_matches_in_memory` |
| Concurrent writers | experience_store | `test_experience_store_concurrency.py::test_parallel_writes_serialize_under_lock` |
| Trace falsification (output-hash mismatch) | trace_diff | `test_trace_diff.py::test_diff_surfaces_output_hash_mismatch` |
| Cross eval-set diff | trace_diff | `test_trace_diff.py::test_diff_rejects_eval_set_mismatch` |
| Causal hypothesis without baseline | failure_analysis | `test_failure_analysis.py::test_mismatched_baseline_is_rejected` |
| Free-form suspected cause | failure_analysis | `test_failure_analysis.py::test_suspected_cause_is_enum_like` |
| Proposer quota exhausted | proposer | `test_proposer.py::test_quota_is_enforced` |

## Out of scope (BATCH-3)

- Per-candidate sandbox containers (currently the candidate runs in the
  evaluator's process; the mutation policy + safety scan are the only
  pre-execution gates).
- LLM-driven proposer with policy-bound prompt template adoption.
- Cross-machine experience store (the current lock is process-local; a
  network filesystem would still serialize but is untested).
- Per-objective weighted Pareto with operator-tunable weights.
