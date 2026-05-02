# F3L-01 Fix Actions — Require PRL Evidence Before APU PR-Update Readiness After CLP Block

Each entry below records a must_fix finding from the F3L-01 red-team
review, the file changed to address it, the test that proves the fix,
the validation command run, and the disposition.

| Finding ID | File changed | Test added/updated | Command run | Disposition |
| --- | --- | --- | --- | --- |
| F3L-01-RT-01 (CLP block treated as PR-update ready without PRL evidence) | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `docs/governance/agent_pr_update_policy.json` | `tests/test_check_agent_pr_update_ready.py::test_clp_block_with_no_prl_evidence_yields_not_ready` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Closed |
| F3L-01-RT-02 (Missing PRL evidence counted present) | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `contracts/schemas/agent_pr_update_ready_result.schema.json` | `tests/test_check_agent_pr_update_ready.py::test_prl_present_status_requires_prl_result_ref_in_artifact` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Closed |
| F3L-01-RT-03 (PRL evidence exists but lacks failure packet refs) | `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `tests/test_check_agent_pr_update_ready.py::test_clp_block_with_prl_evidence_missing_failure_packet_refs_blocks` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Closed |
| F3L-01-RT-04 (PRL evidence exists but lacks repair/eval candidate refs) | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `docs/governance/agent_pr_update_policy.json` | `tests/test_check_agent_pr_update_ready.py::test_clp_block_with_prl_evidence_missing_repair_and_eval_candidates_blocks` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Closed |
| F3L-01-RT-05 (Unknown PRL failure treated as clean) | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `docs/governance/agent_pr_update_policy.json` | `tests/test_check_agent_pr_update_ready.py::test_clp_block_with_prl_unknown_failure_yields_human_review` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Closed |
| F3L-01-RT-06 (PR body prose counted as evidence) | `spectrum_systems/modules/runtime/agent_pr_update_policy.py` (load_prl_result) | `tests/test_check_agent_pr_update_ready.py::test_pr_body_prose_is_not_prl_evidence` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Closed |
| F3L-01-RT-07 (CLP warn treated as clean without policy support) | (no change — existing rule preserved) | `tests/test_check_agent_pr_update_ready.py::test_clp_warn_policy_allowed_does_not_require_prl_evidence`; existing `test_clp_warn_unallowed_reason_blocks` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Closed (no regression) |
| F3L-01-RT-08 (repo_mutating unknown treated as safe) | (no change — existing rule preserved) | existing `tests/test_check_agent_pr_update_ready.py::test_repo_mutating_unknown_yields_not_ready` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Closed (no regression) |
| F3L-01-RT-09 (APU claims authority instead of readiness observation) | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `contracts/schemas/agent_pr_update_ready_result.schema.json` | `tests/test_check_agent_pr_update_ready.py::test_apu_artifact_authority_scope_observation_only`; `tests/test_check_agent_pr_update_ready.py::test_prl_artifact_negated_authority_phrases_absent` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Closed |
| F3L-01-RT-10 (Reserved authority verbs appear in non-owner files) | `docs/reviews/F3L-01_redteam.md`, `docs/review-actions/F3L-01_fix_actions.md`, `tests/test_check_agent_pr_update_ready.py`, `contracts/examples/agent_pr_update_ready_result.example.json`, `docs/governance/agent_pr_update_policy.json`, `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `scripts/check_agent_pr_update_ready.py`, `contracts/schemas/agent_pr_update_ready_result.schema.json` | existing `test_apu_artifact_does_not_claim_owner_authority`; new `test_prl_artifact_negated_authority_phrases_absent` | `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only`; `python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD` | Closed |
| F3L-01-RT-11 (PRL repair attempt count bypasses current policy) | (no change — `max_repair_attempts: 0` and `must_not_do.auto_apply_repairs` preserved) | n/a (out of scope; observation only) | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Out of scope; observation preserved |
| F3L-01-RT-12 (Repeated failures do not create/propose eval regression coverage) | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `docs/governance/agent_pr_update_policy.json` | `tests/test_check_agent_pr_update_ready.py::test_clp_block_with_prl_evidence_missing_repair_and_eval_candidates_blocks` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Closed |

## Test summary

```
python -m pytest tests/test_check_agent_pr_update_ready.py -q
```

Result: 39 passed (12 new F3L-01 cases + 27 existing).

## Authority boundary check

APU is observation-only. The new PRL fields are observation refs.
Canonical authority remains with the systems declared in
`docs/architecture/system_registry.md`. F3L-01 does not redefine PRL,
CLP, AEX, PQX, EVL, TPA, CDE, SEL, LIN, REP, or GOV authority.

## Unresolved must_fix findings

None. All red-team must_fix findings closed by F3L-01 with passing
tests.
