# APR-02 Fix Actions

This file records the disposition of every red-team finding from
`docs/reviews/APR-02_redteam.md`. APR-02 is observation-only (a parity
test); it does not change APR behavior, schemas, or governance mappings.
Canonical authority remains with the canonical owner systems declared in
`docs/architecture/system_registry.md`.

| Finding | File(s) changed | Test added/updated | Command run | Disposition |
|---|---|---|---|---|
| MF-01 APR omits a workflow command | `tests/test_agent_pr_precheck_workflow_parity.py` | `test_workflow_invokes_build_preflight_pqx_wrapper`, `test_apr_wraps_build_preflight_pqx_wrapper`, `test_workflow_invokes_run_contract_preflight`, `test_apr_wraps_run_contract_preflight`, `test_apr_covers_authority_shape_preflight`, `test_apr_covers_authority_leak_guard`, `test_apr_covers_system_registry_guard`, `test_apr_covers_contract_compliance_observation`, `test_apr_covers_generated_artifact_freshness`, `test_apr_covers_selected_tests`, `test_apr_covers_core_loop_pre_pr_gate`, `test_apr_covers_check_agent_pr_ready`, `test_apr_covers_check_agent_pr_update_ready` | `pytest tests/test_agent_pr_precheck_workflow_parity.py -q` | resolved |
| MF-02 APR uses a different execution context | `tests/test_agent_pr_precheck_workflow_parity.py` | `test_workflow_uses_pqx_governed_execution_context`, `test_apr_uses_pqx_governed_execution_context`, `test_apr_pqx_contract_preflight_includes_governed_flags` | `pytest tests/test_agent_pr_precheck_workflow_parity.py -q` | resolved |
| MF-03 APR ignores supplied base/head refs | `tests/test_agent_pr_precheck_workflow_parity.py` | `test_apr_cli_accepts_base_and_head_refs`, `test_apr_phase_wrappers_pass_caller_supplied_refs` (parametrized over five wrappers) | `pytest tests/test_agent_pr_precheck_workflow_parity.py -q` | resolved |
| MF-04 APR uses main/HEAD when explicit refs are supplied | `tests/test_agent_pr_precheck_workflow_parity.py` | `test_apr_phase_wrappers_pass_caller_supplied_refs` asserts the value immediately after `--base-ref`/`--head-ref` is the caller's SHA | `pytest tests/test_agent_pr_precheck_workflow_parity.py -q` | resolved |
| MF-05 APR uses authority-unsafe check labels | `tests/test_agent_pr_precheck_workflow_parity.py` | `test_apr_check_name_labels_remain_authority_safe`, `test_apr_covers_contract_compliance_observation` | `pytest tests/test_agent_pr_precheck_workflow_parity.py -q` | resolved |
| MF-06 workflow changes without APR parity test failing | `tests/test_agent_pr_precheck_workflow_parity.py` | every parity assertion checks both files for the same literal (workflow-side and APR-side asserts paired); single-side regressions surface as a localized test failure | `pytest tests/test_agent_pr_precheck_workflow_parity.py -q` | resolved |
| MF-07 APR treats parity unknown as pass | `tests/test_agent_pr_precheck_workflow_parity.py` | parity test uses plain `assert` (no `xfail`/`skip`); fixtures `assert` the source files exist; `test_parity_test_self_encodes_canonical_strings` self-check guards against silent removal of canonical literals from the parity test itself | `pytest tests/test_agent_pr_precheck_workflow_parity.py -q` | resolved |
| OBS-01 text-based not YAML-parsed | n/a | n/a | n/a | observation; not blocking |
| OBS-02 parity scope limited to APR's six phases | n/a | n/a | n/a | observation; future slice if needed |

No `must_fix` finding is left unresolved. APR-02 ships:

- new file: `tests/test_agent_pr_precheck_workflow_parity.py` (28 tests)
- new file: `docs/reviews/APR-02_redteam.md`
- new file: `docs/review-actions/APR-02_fix_actions.md`

No changes to `scripts/run_agent_pr_precheck.py`,
`.github/workflows/artifact-boundary.yml`, contract schemas, examples,
or governance mappings. APR behavior is unchanged; the parity test is
purely observational.
