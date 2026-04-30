# CLP-01 Fix Actions

All `must_fix` findings from
`docs/reviews/CLP-01_core_loop_pre_pr_gate_redteam.md` are addressed in the
same change set as CLP-01. No unresolved must_fix findings remain.

## Fix log

### MF-01 — PR-ready handoff without authority-shape check
- file changed: `contracts/schemas/core_loop_pre_pr_gate_result.schema.json`,
  `spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py`,
  `scripts/run_core_loop_pre_pr_gate.py`
- test added: `test_missing_required_check_blocks` in
  `tests/test_core_loop_pre_pr_gate.py`
- validation: `python -m pytest tests/test_core_loop_pre_pr_gate.py -q`
- disposition: fixed

### MF-02 — PR-ready handoff without authority-leak guard
- file changed: same schema + helper + runner
- test added: `test_missing_authority_leak_blocks`
- validation: `python -m pytest tests/test_core_loop_pre_pr_gate.py -q`
- disposition: fixed

### MF-03 — PR-ready handoff with stale TLS artifact
- file changed: `spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py`
  (`hash_paths`, `diff_hash_maps`), `scripts/run_core_loop_pre_pr_gate.py`
  (`_check_tls_freshness`)
- test added: `test_tls_freshness_drift_blocks`,
  `test_tls_freshness_skip_blocks_repo_mutating`
- validation: `python -m pytest tests/test_core_loop_pre_pr_gate.py -q`
- disposition: fixed

### MF-04 — PR-ready handoff with contract schema violation
- file changed: `scripts/run_core_loop_pre_pr_gate.py`
  (`_check_contract_preflight` reads
  `control_signal.strategy_gate_decision`)
- test added: `test_contract_preflight_block_propagates`
- validation: `python -m pytest tests/test_core_loop_pre_pr_gate.py -q`
- disposition: fixed

### MF-05 — Missing check output counted as pass
- file changed: schema (`$defs/check.allOf` requires `output_ref` when
  `status` is pass/warn/block), helper (`build_check` and `evaluate_gate`)
- test added: `test_missing_required_check_output_blocks`
- validation: `python -m pytest tests/test_core_loop_pre_pr_gate.py -q`
- disposition: fixed

### MF-06 — Unknown failure counted as warn
- file changed: helper `KNOWN_FAILURE_CLASSES` + `evaluate_gate` upgrades
  unknown failure to block + `human_review_required=true`. Schema's
  pass-branch `allOf` forbids `human_review_required=true` when
  `gate_status=pass`.
- test added: `test_unknown_failure_class_requires_human_review`
- validation: `python -m pytest tests/test_core_loop_pre_pr_gate.py -q`
- disposition: fixed

### MF-07 — CLP claims approval/certification/promotion/enforcement authority
- file changed: schema pins `authority_scope` to const `observation_only`;
  registry entry under "Recurring Cross-System Phase Labels (Non-Owner)"
  enumerates `must_not_do` for every authority verb.
- test added: `test_authority_scope_remains_observation_only`,
  `test_clp_does_not_claim_authority`
- validation: `python -m pytest tests/test_core_loop_pre_pr_gate.py -q`
- disposition: fixed

### MF-08 — Repo-mutating work skips selected tests
- file changed: `scripts/run_core_loop_pre_pr_gate.py`
  (`_check_selected_tests` uses canonical `pr_test_selection.resolve_required_tests`
  and `is_docs_only_non_governed`); helper `evaluate_gate` converts
  any missing required check into a block on repo-mutating work.
- test added: `test_selected_tests_failure_blocks`,
  `test_selected_tests_skip_in_repo_mutating_blocks`
- validation: `python -m pytest tests/test_core_loop_pre_pr_gate.py -q`
- disposition: fixed

### MF-09 — Generated-artifact freshness check can be bypassed
- file changed: helper `hash_paths`/`diff_hash_maps`; runner
  `_check_tls_freshness`; schema (status enum disallows arbitrary values)
- test added: `test_tls_freshness_drift_blocks`,
  `test_tls_freshness_skip_blocks_repo_mutating`
- validation: `python -m pytest tests/test_core_loop_pre_pr_gate.py -q`
- disposition: fixed

### MF-10 — Gate passes when contract_preflight blocks
- file changed: helper `evaluate_gate`; schema's pass-branch `allOf`
  requires `first_failed_check=null` and `human_review_required=false`
  when `gate_status=pass`.
- test added: `test_contract_preflight_block_propagates`,
  `test_gate_pass_only_when_all_required_checks_pass`
- validation: `python -m pytest tests/test_core_loop_pre_pr_gate.py -q`
- disposition: fixed

### MF-11 — AEX/PQX ignore missing CLP evidence
- file changed: `spectrum_systems/modules/runtime/agent_core_loop_proof.py`
  (added `clp_evidence_artifact` parameter; missing/blocked CLP evidence
  forces `compliance_status=BLOCK` and emits a `clp_evidence_missing` /
  `resolve_clp_block` learning action with `owner_system=PRL`).
- test added: `test_agl_reports_missing_clp_evidence_for_repo_mutating_work`,
  `test_agl_blocks_when_clp_gate_status_is_block`,
  `test_agl_passes_when_clp_evidence_is_complete_pass` (sanity)
- validation: `python -m pytest tests/test_core_loop_pre_pr_gate.py
  tests/test_agent_core_loop_proof.py -q`
- disposition: fixed
