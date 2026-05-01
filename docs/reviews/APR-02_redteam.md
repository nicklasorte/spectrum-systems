# APR-02 Red-Team Review — APR Workflow Parity Test

Categories: `must_fix` (blocks the PR), `should_fix` (open follow-up
before the next dependent slice), `observation` (informational).

APR-02 adds a parity test only. It does not change APR behavior, schemas,
or governance mappings. The test asserts that
`scripts/run_agent_pr_precheck.py` covers the same essential governed-
preflight commands and flags that
`.github/workflows/artifact-boundary.yml`'s `governed-contract-preflight`
job runs. The test emits readiness observations only (pytest pass/fail);
canonical authority remains with the canonical owner systems declared in
`docs/architecture/system_registry.md`.

Every finding below names the failure mode the parity test must catch
and the assertion that closes it.

## Findings

### MF-01 — APR omits a workflow command
- **Risk:** APR drops one of the canonical preflight scripts (e.g.
  `build_preflight_pqx_wrapper.py` or `run_contract_preflight.py`),
  letting a developer pass APR locally while CI fails.
- **Mitigation:** the parity test reads both files as text and asserts
  each canonical script name appears in both APR and the workflow:
  `test_workflow_invokes_build_preflight_pqx_wrapper`,
  `test_apr_wraps_build_preflight_pqx_wrapper`,
  `test_workflow_invokes_run_contract_preflight`,
  `test_apr_wraps_run_contract_preflight`, plus per-surface coverage
  tests (`test_apr_covers_authority_shape_preflight`,
  `test_apr_covers_authority_leak_guard`,
  `test_apr_covers_system_registry_guard`,
  `test_apr_covers_contract_compliance_observation`,
  `test_apr_covers_generated_artifact_freshness`,
  `test_apr_covers_selected_tests`,
  `test_apr_covers_core_loop_pre_pr_gate`,
  `test_apr_covers_check_agent_pr_ready`,
  `test_apr_covers_check_agent_pr_update_ready`).
- **Disposition:** resolved.

### MF-02 — APR uses a different execution context
- **Risk:** APR runs `run_contract_preflight` without
  `--execution-context pqx_governed`, flipping the strategy gate to a
  warn-only path while CI uses pqx_governed.
- **Mitigation:** the parity test asserts both files contain
  `--execution-context pqx_governed`
  (`test_workflow_uses_pqx_governed_execution_context`,
  `test_apr_uses_pqx_governed_execution_context`). The runtime test
  `test_apr_pqx_contract_preflight_includes_governed_flags` invokes
  `pqx_contract_preflight` with monkeypatched subprocess and asserts
  the constructed cmd includes `--execution-context pqx_governed`.
- **Disposition:** resolved.

### MF-03 — APR ignores supplied base/head refs
- **Risk:** caller passes explicit refs (e.g. CI-discovered SHAs); APR
  silently overrides them with `origin/main..HEAD`.
- **Mitigation:**
  `test_apr_phase_wrappers_pass_caller_supplied_refs` parametrizes over
  the five ref-consuming wrappers (`tpa_authority_shape`,
  `tpa_authority_leak`, `tpa_system_registry`, `pqx_build_wrapper`,
  `pqx_contract_preflight`), monkeypatches `_run_subprocess`, calls each
  with synthetic SHAs `abc1234deadbeef` / `def5678cafebabe`, and asserts
  both SHAs land directly after `--base-ref` and `--head-ref` in the
  constructed cmd.
- **Disposition:** resolved.

### MF-04 — APR uses main/HEAD when explicit refs are supplied
- **Risk:** even if APR accepts `--base-ref` / `--head-ref` at the CLI,
  internal wrappers could substitute defaults at the subprocess call
  site.
- **Mitigation:** same parity test
  (`test_apr_phase_wrappers_pass_caller_supplied_refs`) asserts the
  *value* immediately following `--base-ref` and `--head-ref` is the
  caller-supplied SHA — not `main` or `HEAD`.
- **Disposition:** resolved.

### MF-05 — APR uses authority-unsafe check labels
- **Risk:** APR exposes the canonical compliance-runner filename (which
  carries a reserved authority subtoken) as a `check_name`, polluting
  the observation surface with an authority-claim shape.
- **Mitigation:** `test_apr_check_name_labels_remain_authority_safe`
  asserts the APR source contains no
  `check_name="run_contract_enforcement"` (or single-quoted equivalent)
  and no `phase="ENF"`. Independently,
  `test_apr_covers_contract_compliance_observation` asserts
  `tpa_contract_compliance_observation` is the visible label and that
  APR resolves the canonical runner's filename dynamically via
  `_resolve_compliance_gate_runner` rather than embedding the literal
  name.
- **Disposition:** resolved.

### MF-06 — workflow changes without APR parity test failing
- **Risk:** CI workflow drifts (renames a script, drops a flag); APR
  parity test does not detect the drift because it only tests in one
  direction.
- **Mitigation:** every parity assertion checks *both* files for the
  same literal. If the workflow drops `scripts/run_contract_preflight.py`,
  `test_workflow_invokes_run_contract_preflight` fails. If APR drops it,
  `test_apr_wraps_run_contract_preflight` fails. If either side drops
  `--execution-context pqx_governed`, `--pqx-wrapper-path`, or
  `--authority-evidence-ref`, the corresponding pair of asserts fails.
- **Disposition:** resolved.

### MF-07 — APR treats parity unknown as pass
- **Risk:** the parity test silently `xfails`, skips, or no-ops if a
  required literal is missing — letting drift pass undetected.
- **Mitigation:** the parity test uses plain `assert` statements
  (no `pytest.skip`, no `xfail`). The fixtures `workflow_text` /
  `apr_text` `assert` the underlying files exist. The
  `test_parity_test_self_encodes_canonical_strings` self-check asserts
  the parity test source itself still contains every canonical literal
  it relies on, so silent removal of an assertion is detected.
- **Disposition:** resolved.

### OBS-01 — Parity test is text-based, not a YAML semantic parser
- **Observation:** the parity test reads both files as text and asserts
  on substring presence. This is intentional: the repo has no `yaml`
  dependency in `requirements-dev.txt`, and the task explicitly allows
  a practical text-match test. A future slice could harden the test to
  a YAML-parsed assertion if PyYAML is added to the dev deps.
- **Disposition:** observation only; not blocking.

### OBS-02 — Parity scope is limited to APR's six phases
- **Observation:** APR's PHASES are `(AEX, TPA, PQX, EVL, CDE, SEL)`.
  The parity test covers the surfaces APR currently wraps. If CI adds
  a *new* surface that APR does not yet wrap, the parity test as
  written cannot detect that — only drift on already-covered surfaces.
  This matches the task's stated scope ("essential governed-contract /
  preflight command sequence"); a broader "every workflow step has an
  APR wrapper" check is out of scope for APR-02.
- **Disposition:** observation only; future slice if needed.
