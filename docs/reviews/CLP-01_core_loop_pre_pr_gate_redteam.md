# CLP-01 Core Loop Pre-PR Gate Red-Team Review

Scope: `core_loop_pre_pr_gate_result` schema, `scripts/run_core_loop_pre_pr_gate.py`,
`spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py`, AGL integration in
`spectrum_systems/modules/runtime/agent_core_loop_proof.py`.

Authority scope under review: observation_only. Final authorities (AEX/PQX/EVL/
TPA/CDE/SEL) are out of scope and untouched by this work.

## must_fix

1. **PR-ready handoff without authority-shape check.**
   Attack: agent emits a CLP gate result that omits the `authority_shape_preflight`
   check entirely.
   Resolution: schema requires `checks` array; runner unconditionally appends a
   check entry for every name in `REQUIRED_CHECK_NAMES`; `evaluate_gate` blocks
   when `repo_mutating=true` and any required `check_name` is absent
   (`failure_classes` includes `missing_required_check_output`).
   Files: `contracts/schemas/core_loop_pre_pr_gate_result.schema.json`,
   `spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py`.
   Test: `test_missing_required_check_blocks` in
   `tests/test_core_loop_pre_pr_gate.py`.
   Disposition: fixed.

2. **PR-ready handoff without authority-leak guard.**
   Attack: agent removes `authority_leak_guard` from the bundle.
   Resolution: same fail-closed rule as #1; the leak guard is in
   `REQUIRED_CHECK_NAMES`.
   Test: `test_missing_authority_leak_blocks`.
   Disposition: fixed.

3. **PR-ready handoff with stale TLS artifact.**
   Attack: agent reports `tls_generated_artifact_freshness=pass` but the
   underlying generated artifact has not been regenerated.
   Resolution: runner hashes the canonical TLS / ecosystem-health artifact set
   before and after running both generators; any post-run hash drift produces
   `status=block` with `failure_class=tls_generated_artifact_stale`.
   Helper-level test: `test_tls_freshness_drift_blocks` exercises the
   block path through `build_check`/`evaluate_gate`.
   Disposition: fixed.

4. **PR-ready handoff with contract schema violation.**
   Attack: contract preflight reports BLOCK or FREEZE but the gate still
   returns pass.
   Resolution: `_check_contract_preflight` reads
   `contract_preflight_result_artifact.json`'s `control_signal.strategy_gate_decision`
   and maps `BLOCK`/`FREEZE` to a CLP block check.
   Test: `test_contract_preflight_block_propagates`.
   Disposition: fixed.

5. **Missing check output counted as pass.**
   Attack: a check is recorded as `status=pass` but `output_ref` is null/empty.
   Resolution: schema's per-check `allOf` requires `output_ref` to be a
   non-empty string when `status` is `pass`/`warn`/`block`. Helper
   `build_check` raises `ValueError` if a non-skipped status omits
   `output_ref`. `evaluate_gate` also defensively re-checks `output_ref`.
   Test: `test_missing_required_check_output_blocks`.
   Disposition: fixed.

6. **Unknown failure counted as warn.**
   Attack: a check returns `failure_class` outside the `KNOWN_FAILURE_CLASSES`
   set, hoping the gate degrades to warn.
   Resolution: `evaluate_gate` forces `gate_status=block` AND
   `human_review_required=true` whenever any required-check failure_class is
   not in the known set. The schema's pass-branch `allOf` also forbids
   `human_review_required=true` when `gate_status=pass`.
   Test: `test_unknown_failure_class_requires_human_review`.
   Disposition: fixed.

7. **CLP claims approval/certification/promotion/enforcement authority.**
   Attack: a CLP artifact is emitted with `authority_scope` other than
   `observation_only` to imply binding authority.
   Resolution: schema pins `authority_scope` to the constant
   `"observation_only"`. Helper `build_gate_result` always sets that value.
   Registry entry under "Recurring Cross-System Phase Labels (Non-Owner)"
   explicitly enumerates `must_not_do` for every authority verb.
   Test: `test_authority_scope_remains_observation_only`,
   `test_clp_does_not_claim_authority`.
   Disposition: fixed.

8. **Repo-mutating work skips selected tests.**
   Attack: agent claims `selected_tests` is not required for a repo-mutating
   change (e.g. `--skip selected_tests`).
   Resolution: `_check_selected_tests` only emits `pass` for non-governed
   docs-only diffs (via canonical `is_docs_only_non_governed`). On governed
   changes with no resolved test targets, it emits `status=block` with
   `failure_class=pytest_selection_missing`. On non-zero pytest exit, it
   emits `status=block` with `failure_class=selected_test_failure`.
   The CLI `--skip` flag deliberately leaves the required check name out of
   `seen`, which `evaluate_gate` then converts into a
   `missing_required_check_output` block (so `--skip` cannot be used to mask
   a failing test selection in repo-mutating mode).
   Test: `test_selected_tests_failure_blocks`,
   `test_selected_tests_skip_in_repo_mutating_blocks`.
   Disposition: fixed.

9. **Generated-artifact freshness check can be bypassed.**
   Attack: agent forces the freshness check to `status=pass` while the
   on-disk artifact would change if regenerated.
   Resolution: the freshness check is part of the canonical CLI bundle; the
   helper module exposes `hash_paths`/`diff_hash_maps` which are deterministic
   and used both by the runner and by the test suite to assert that drift
   forces a block status. There is no "skip on success" path: `--skip
   tls_generated_artifact_freshness` removes the check from the bundle, which
   the gate evaluator turns into a `missing_required_check_output` block on
   repo-mutating work.
   Test: `test_tls_freshness_drift_blocks`,
   `test_tls_freshness_skip_blocks_repo_mutating`.
   Disposition: fixed.

10. **Gate passes when contract_preflight blocks.**
    Attack: `contract_preflight` returns block but the surrounding gate
    aggregator returns pass.
    Resolution: any required check at `status=block` raises
    `gate_status=block` in `evaluate_gate`. Schema's allOf prevents
    `gate_status=pass` from coexisting with a non-null `first_failed_check`.
    Test: `test_contract_preflight_block_propagates`,
    `test_gate_pass_only_when_all_required_checks_pass`.
    Disposition: fixed.

11. **AEX/PQX ignore missing CLP evidence.**
    Attack: a repo-mutating agent slice produces an `agent_core_loop_run_record`
    without consuming any CLP evidence; AGL silently passes.
    Resolution: `build_agent_core_loop_record` now accepts
    `clp_evidence_artifact`. When the slice is repo-mutating and no valid
    CLP evidence file is loaded, the builder injects a learning action
    (`owner_system=PRL`, `reason_code=clp_evidence_missing`) and forces
    `compliance_status=BLOCK`. When the loaded CLP evidence has
    `gate_status=block`, the builder records a `resolve_clp_block` learning
    action and (for repo-mutating slices) forces BLOCK. Final authority
    over admission/closure remains with AEX/PQX; AGL only surfaces the
    missing or failed pre-PR gate evidence.
    Test: `test_agl_reports_missing_clp_evidence_for_repo_mutating_work`,
    `test_agl_blocks_when_clp_gate_status_is_block`.
    Disposition: fixed.

## should_fix

- **CLP runner subprocess flakiness.** The runner shells out via
  `subprocess.run`. If a system-level signal (OOM, SIGTERM) terminates a
  child process with a non-standard returncode, the corresponding check
  becomes block — which is the correct fail-closed behavior — but the
  CLP artifact does not currently distinguish "tool crashed" from "tool
  reported a violation." Future hardening should normalize the failure
  class against PRL's vocabulary.
- **Selected-tests pytest selection cost.** `resolve_required_tests`
  reads every `tests/test_*.py` file in the repository to perform needle
  matches. On large repos this is O(N_tests * N_changed_files); CLP-01
  reuses the canonical selector deliberately, but a future improvement
  could cache the inventory.
- **Provenance fields.** The current schema does not model
  workflow_run_id / source_commit_sha. PRL-style provenance can be added
  in a future revision.

## observation

- CLP is intentionally a thin wrapper: it does not re-implement any
  preflight logic; it only invokes the canonical scripts and aggregates
  their results. This avoids duplicating authority logic.
- The schema deliberately models `failure_classes` as a free-string
  array (rather than a bound enum) so that downstream PRL classification
  can extend the vocabulary without forcing a CLP schema change. The
  guardrail is `KNOWN_FAILURE_CLASSES` in the runtime helper plus the
  `human_review_required=true` rule for unknown classes — this keeps the
  fail-closed surface explicit.
- `--max-repair-attempts` defaults to 0 and is currently unused. Repair
  authority belongs to PRL/FRE/CDE/PQX; CLP-01 only observes.
- The CLI exit codes (0=pass, 1=warn, 2=block) match the canonical
  preflight precedent in `scripts/run_contract_preflight.py`. CI hooks
  should treat any non-zero exit as a block on the PR-ready handoff.
