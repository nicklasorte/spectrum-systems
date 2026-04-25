# HOP-003C-004 — Phase 2 Red-Team Review

**Scope:** the Phase 2 surface added by HOP-003C-004:
held-out eval set, `promotion_readiness.py`, `rollback_signals.py`,
`eval_factory.py`, `trend_reports.py`, `control_integration.py`, the
corresponding schemas, and the sandbox additions.

**Outcome:** all six attack classes are closed. Concrete findings, fixes,
and tests below. The fix pass is included in this PR.

## Attack matrix

| # | Attack class                                  | Vector                                                                                                  | Status   | Fix / mitigation                                                                                                                        |
|---|-----------------------------------------------|---------------------------------------------------------------------------------------------------------|----------|------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | Readiness bypass — fabricated `ready_signal`  | Caller hand-builds a `hop_harness_release_readiness_signal` with `readiness_signal=ready_signal` and a failed rationale row. | CLOSED   | Schema `allOf` `if/then`: `readiness_signal=="ready_signal"` ⇒ every rationale item `passed=true`. Test: `test_attack_fabricated_ready_artifact_rejected_by_schema`. |
| 2 | Eval gaming — unadmitted score artifact       | Caller passes an in-memory score never written to the store, bypassing evaluator + sandbox.             | CLOSED   | New `scores_admitted` check: builder scans the index for both score artifact ids before yielding `ready_signal`. Test: `test_attack_unadmitted_score_yields_risk_signal`. |
| 3 | Regression leakage — case-id collision        | Eval factory emits a candidate case whose id collides with a live search-set case (auto-pass).          | CLOSED   | Factory id template `hop_case_<category>_<source>` namespaces by category and source artifact id. Test: `test_attack_eval_factory_does_not_collide_with_search_set`. |
| 4 | Rollback failure — re-readiness               | A candidate has a quarantine signal recorded, then the readiness builder is run again and yields `ready_signal`. | CLOSED   | `candidate_not_quarantined` check consults `hop_harness_rollback_signal` artifacts and forces `risk_signal` on match. REL remains the canonical owner. Test: `test_attack_quarantined_candidate_yields_risk_signal`. |
| 5 | Control bypass — `advisory_only=False`        | Caller smuggles a payload with `advisory_only=false` into the store.                                    | CLOSED   | All five Phase 2 schemas pin `advisory_only` to `const: true`. Test: `test_attack_advisory_only_false_rejected_by_schema`. |
| 6 | Eval-data read leakage — sandbox reads        | Malicious harness reads `contracts/evals/hop_heldout/cases/*.json` and memorises answers.               | CLOSED   | Sandbox now accepts `denied_read_path_prefixes`; the evaluator denies the entire `contracts/evals/` subtree on every case. Test: `test_attack_sandbox_blocks_eval_data_reads`. |

## Notes on each finding

### 1. Schema-level ready/rationale coupling

Before: a hand-built signal with `readiness_signal=ready_signal` plus a
failed rationale row would validate. A consumer reading it could be
misled into thinking every check passed.

After: the schema's `allOf.if.then` clause makes
`readiness_signal="ready_signal"` invalid unless **every** rationale
item has `passed=true`. There is no path from `passed=false` to
`ready_signal` that survives schema validation. The other two values
(`warn_signal`, `risk_signal`) carry no readiness implication on their
own.

### 2. Score artifact must be admitted

Before: the readiness builder only validated the score *shape*. A
caller could synthesise a score that no evaluator ever produced — i.e.
no sandbox run, no traces. The signal would still pass the threshold
checks.

After: the builder enumerates the store index and refuses to yield
`ready_signal` unless **both** `search_score.artifact_id` and
`heldout_score.artifact_id` are present. The store admits scores only
after sandbox-evaluated runs.

### 3. Eval-factory id discipline

The factory's case-id template is
`hop_case_<category>_<slugified(candidate_id_<source_artifact_id>)>` —
the source artifact id is a content-hash-derived suffix, so collisions
with the existing search set (whose ids use a stable English slug) are
not possible by construction. The test asserts this invariant against
the live search set.

### 4. Quarantine signal is binding

Before: `rollback_signals.emit_rollback_signal(recommended_action="quarantine", ...)`
produced an audit record that the readiness builder ignored.

After: the builder's `candidate_not_quarantined` check streams the index
for any rollback signal whose `subject_candidate_id` matches and whose
`recommended_action` is `quarantine`. A match forces
`readiness_signal=risk_signal`. The harness consumes the advisory signal;
**REL** remains the canonical release/rollback owner that decides
whether to act on it.

### 5. `advisory_only=true` is structural, not optional

Each Phase 2 schema declares `"advisory_only": {"const": true}` and a
`"delegates_to"` field that names the canonical owner(s) (REL/CDE/SEL).
JSON-Schema `const` is exact-match; a `false` literal fails validation.
This is a class-wide guarantee for the Phase 2 surface:

- `harness_release_readiness_signal`
- `harness_rollback_signal`
- `harness_eval_factory_record`
- `harness_trend_report`
- `harness_control_advisory`

### 6. Sandbox read-leakage closure

`SandboxConfig.denied_read_path_prefixes` is a tuple of absolute path
roots that the child process refuses to read. The evaluator passes
`<repo>/contracts/evals` as a denied root for every case, blocking
both search and held-out cases regardless of which set is active.

The denial is enforced through the same `_install_guards` chain as the
existing write-protection, covering `builtins.open`, `os.open`, and
`pathlib.Path.open`. A read attempt yields
`sandbox_violation:read_denied_eval_data:<path>` — surfaced via
`SandboxResult.violation_type="sandbox_violation"` and pulled into a
`hop_harness_failure_hypothesis` artifact by the evaluator.

## Residual risks

- Read-leakage closure depends on the candidate using only the
  intercepted entry points. A C-extension that calls `syscall(2)` would
  bypass the Python guards. Out of scope; mitigated at the OS layer in
  production deployments via seccomp / pivot_root.
- Eval factory output is *advisory*; it never materialises the new
  cases on disk. Materialisation is a separate, gated process owned by
  governance.
- The readiness builder consults the store at signal-emission time. A
  racing writer that admits a score artifact between the index scan
  and the signal write is possible in principle; the store's exclusive
  flock on `index.jsonl.lock` plus the signal artifact's content hash
  mean the race produces a stale-but-consistent signal rather than an
  incorrect one. Canonical owners re-read on consumption.
- HOP does not sign manifests. A privileged process that swaps
  `contracts/evals/.../manifest.json` between runs could change the
  search/held-out boundary. This is a deployment concern; HOP fails
  closed on hash mismatches but cannot detect a fully-replaced
  manifest. Out of scope for Phase 2 (governance system handles this).

## Verification

```bash
python -m pytest tests/hop/test_phase2_red_team.py \
                 tests/hop/test_promotion_readiness.py \
                 tests/hop/test_rollback_signals.py \
                 tests/hop/test_eval_factory.py \
                 tests/hop/test_trend_reports.py \
                 tests/hop/test_control_integration.py \
                 tests/hop/test_heldout_eval.py \
                 tests/hop/test_sandbox.py -q
```
