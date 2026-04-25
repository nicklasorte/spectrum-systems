# HOP-003C-004 — Phase 2 Red-Team Review

**Scope:** the Phase 2 surface added by HOP-003C-004:
held-out eval set, `promotion_gate.py`, `rollback_signals.py`, `eval_factory.py`,
`trend_reports.py`, `control_integration.py`, the corresponding schemas,
and the sandbox additions.

**Outcome:** all six attack classes are closed. Concrete findings, fixes,
and tests below. The fix pass is included in this PR.

## Attack matrix

| # | Attack class                              | Vector                                                                                                  | Status   | Fix / mitigation                                                                                                                        |
|---|-------------------------------------------|---------------------------------------------------------------------------------------------------------|----------|------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | Promotion bypass — fabricated `allow`     | Caller hand-builds a `hop_harness_promotion_decision` with `decision=allow` and a failed rationale row. | CLOSED   | Schema `allOf` `if/then`: `decision=="allow"` ⇒ every rationale item `passed=true`. Test: `test_attack_fabricated_allow_artifact_rejected_by_schema`. |
| 2 | Eval gaming — unadmitted score artifact   | Caller passes an in-memory score never written to the store, bypassing evaluator + sandbox.             | CLOSED   | New `scores_admitted` check: gate scans the index for both score artifact ids before allowing. Test: `test_attack_unadmitted_score_blocks_promotion`. |
| 3 | Regression leakage — case-id collision    | Eval factory emits a candidate case whose id collides with a live search-set case (auto-pass).          | CLOSED   | Factory id template `hop_case_<category>_<source>` namespaces by category and source artifact id. Test: `test_attack_eval_factory_does_not_collide_with_search_set`. |
| 4 | Rollback failure — re-promotion           | A candidate is quarantined, then the gate is run again and returns `allow`.                             | CLOSED   | New `candidate_not_quarantined` check: gate consults `hop_harness_rollback_signal` artifacts before allowing. Test: `test_attack_quarantined_candidate_blocked_at_promotion`. |
| 5 | Control bypass — `advisory_only=False`    | Caller smuggles a payload with `advisory_only=false` into the store.                                    | CLOSED   | All five new schemas pin `advisory_only` to `const: true`. Test: `test_attack_advisory_only_false_rejected_by_schema`. |
| 6 | Eval-data read leakage — sandbox reads    | Malicious harness reads `contracts/evals/hop_heldout/cases/*.json` and memorises answers.               | CLOSED   | Sandbox now accepts `denied_read_path_prefixes`; the evaluator denies the entire `contracts/evals/` subtree on every case. Test: `test_attack_sandbox_blocks_eval_data_reads`. |

## Notes on each finding

### 1. Schema-level allow/rationale coupling

Before: the schema accepted any `decision` value with any rationale shape.
A bad-faith caller could write `{"decision": "allow", "rationale": [{"passed": false}]}`
and the artifact would validate. The control plane reading it could be misled.

After: the schema's `allOf.if.then` clause makes
`decision="allow"` invalid unless **every** rationale item has
`passed=true`. There is no path from `passed=false` to `decision=allow`
that survives schema validation.

### 2. Score artifact must be admitted

Before: `evaluate_promotion` only validated the score *shape*. A caller
could synthesise a score that no evaluator ever produced — i.e. no
sandbox run, no traces. The decision would still pass the threshold
checks.

After: the gate enumerates the store index and refuses unless **both**
`search_score.artifact_id` and `heldout_score.artifact_id` are present.
The store admits scores only after sandbox-evaluated runs.

### 3. Eval-factory id discipline

The factory's case-id template is
`hop_case_<category>_<slugified(candidate_id_<source_artifact_id>)>` —
the source artifact id is a content-hash-derived suffix, so collisions
with the existing search set (whose ids use a stable English slug) are
not possible by construction. The test asserts this invariant against
the live search set.

### 4. Quarantine is binding

Before: `rollback_signals.emit_rollback_signal(recommended_action="quarantine", ...)`
produced an audit record that the gate ignored.

After: the gate's `candidate_not_quarantined` check streams the index
for any rollback signal whose `subject_candidate_id` matches and whose
`recommended_action` is `quarantine`. A match forces `decision=block`.
The gate consumes the advisory signal; REL remains the canonical
release/rollback owner that decides whether to act on it.

### 5. `advisory_only=true` is structural, not optional

Each new schema declares `"advisory_only": {"const": true}`. JSON-Schema
`const` is exact-match; a `false` literal fails validation. This is a
class-wide guarantee for the Phase 2 surface:

- `harness_promotion_decision`
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
- The promotion gate consults the store at decision time. A racing
  writer that admits a score artifact between the index scan and the
  decision write is possible in principle; the store's exclusive flock
  on `index.jsonl.lock` plus the decision artifact's content hash mean
  the race produces a stale-but-consistent decision rather than an
  incorrect one. The control plane re-reads on consumption.
- HOP does not sign manifests. A privileged process that swaps
  `contracts/evals/.../manifest.json` between runs could change the
  search/held-out boundary. This is a deployment concern; HOP fails
  closed on hash mismatches but cannot detect a fully-replaced
  manifest. Out of scope for Phase 2 (governance system handles this).

## Verification

```bash
python -m pytest tests/hop/test_phase2_red_team.py \
                 tests/hop/test_promotion_gate.py \
                 tests/hop/test_rollback_signals.py \
                 tests/hop/test_eval_factory.py \
                 tests/hop/test_trend_reports.py \
                 tests/hop/test_control_integration.py \
                 tests/hop/test_heldout_eval.py \
                 tests/hop/test_sandbox.py -q
```
