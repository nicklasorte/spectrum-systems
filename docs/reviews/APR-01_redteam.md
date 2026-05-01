# APR-01 Red-Team Review — Agent PR Precheck Runner

Categories: `must_fix` (blocks the PR), `should_fix` (open follow-up before
the next dependent slice), `observation` (informational).

APR-01 is observation-only. It surfaces pre-PR readiness inputs and
compliance observations only. Canonical authority remains with AEX, PQX,
EVL, TPA, CDE, SEL, LIN, REP, and GOV per
`docs/architecture/system_registry.md`. Each finding below names the
canonical owner whose authority the finding pretends to claim, and the
mitigation that keeps APR-01 inside its observation envelope.

## Findings

### MF-01 — APR treats a missing CLP-01 / CLP-02 artifact as pass
- **Risk:** if the CLP runner crashes or the artifact path is missing, APR
  silently aggregates as pass and lets the agent push.
- **Mitigation:** the CDE-phase wrappers (`cde_core_loop_pre_pr_gate`,
  `cde_check_agent_pr_ready`) treat any non-zero exit as
  `status=block` with a reason code. The output artifact reference is
  only added when the file exists on disk; otherwise the check stays
  blocking.
- **Test:** `test_missing_clp_blocks_pr_ready`.
- **Disposition:** resolved.

### MF-02 — APR treats a missing APU artifact as pass
- **Risk:** the SEL-phase APU runner is the final readiness gate; if its
  artifact is missing, APR could mark `pr_update_ready_status=ready`.
- **Mitigation:** `sel_check_agent_pr_update_ready` is a subprocess wrapper
  whose `status` is `pass` only when the canonical APU output file
  exists AND the script exited zero. Otherwise APR records
  `apu_pr_update_not_ready`.
- **Test:** `test_missing_apu_blocks_pr_update_ready`.
- **Disposition:** resolved.

### MF-03 — APR treats `unknown` as `present`
- **Risk:** a check status of `unknown` could be silently rolled up as
  pass.
- **Mitigation:** the schema's `$defs.check.allOf` rejects `status=pass`
  without `output_artifact_refs.minItems=1`, AND
  `status ∈ {warn, block, skipped, missing, unknown}` requires
  `reason_codes.minItems=1`. The aggregator places `unknown` in
  `_BLOCKING_STATUSES`, so any unknown forces overall `block`.
- **Test:** `test_non_pass_without_reason_codes_is_schema_invalid`
  (parametrized over the five non-pass statuses).
- **Disposition:** resolved.

### MF-04 — APR accepts PR body or commit prose as evidence
- **Risk:** an agent could substitute commit-message text for an
  artifact reference.
- **Mitigation:** the schema requires `output_artifact_refs` to be a
  non-empty array of strings on `status=pass`. The runtime never
  populates `output_artifact_refs` from anywhere except the on-disk
  presence of the canonical per-gate artifact path.
- **Test:** `test_pr_body_prose_does_not_satisfy_artifact_refs`.
- **Disposition:** resolved.

### MF-05 — APR runs different commands than CI runs
- **Risk:** APR diverges from CI's `governed-contract-preflight` job
  over time.
- **Mitigation:** every subprocess command in `scripts/run_agent_pr_precheck.py`
  uses the same flags CI uses (`--execution-context pqx_governed`,
  `--authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json`,
  `--candidates ""`, etc.). The example artifact's `command` strings
  match the CI workflow YAML by inspection. A future drift would surface
  as a CI-vs-APR mismatch on the next PR; a follow-up red-team finding
  could pin the commands via a contract.
- **Test:** N/A unit test; `should_fix` follow-up to add a
  workflow-vs-runner string-match test.
- **Disposition:** observation; `should_fix` follow-up filed.

### MF-06 — APR mis-resolves explicit base/head refs back to `main..HEAD`
- **Risk:** a user passes explicit SHAs; APR silently falls back to
  `origin/main..HEAD`.
- **Mitigation:** the CLI parser sets `--base-ref origin/main` and
  `--head-ref HEAD` only as defaults; user-supplied values are passed
  through unchanged to every subprocess. `_git_diff_name_only` uses
  the supplied refs verbatim.
- **Test:** `test_replay_apu_3ls_01_missing_required_surface_mapping`
  exercises the AEX path with synthetic refs.
- **Disposition:** resolved.

### MF-07 — APR misses contract preflight `pqx_governed` mode
- **Risk:** APR runs preflight without `--execution-context pqx_governed`,
  flipping the strategy gate to a warn-only path.
- **Mitigation:** `pqx_contract_preflight` always passes
  `--execution-context pqx_governed` and the canonical authority
  evidence ref.
- **Test:** the example artifact's `pqx_governed_contract_preflight`
  check entry is the CI command verbatim.
- **Disposition:** resolved.

### MF-08 — APR misses generated-artifact freshness or runs only once
- **Risk:** a single regenerator run can mask non-determinism.
- **Mitigation:** `evl_generated_artifact_freshness` runs the TLS +
  ecosystem regenerators twice and compares structurally normalized
  snapshots. Drift between runs blocks; non-zero exits block.
- **Test:** `test_tls_ecosystem_stale_blocks`.
- **Disposition:** resolved.

### MF-09 — APR misses authority-shape / authority-leak / system-registry
- **Risk:** any of the three TPA-phase guards could be skipped.
- **Mitigation:** all three are unconditional subprocess phases under the
  TPA group. They run on every invocation unless the user explicitly
  passes `--skip-phase TPA` (debug only). Each writes its canonical
  artifact path; missing artifact → block.
- **Test:** `test_authority_shape_failure_surfaces_artifact_ref`,
  `test_system_registry_failure_surfaces_artifact_ref`.
- **Disposition:** resolved.

### MF-10 — APR treats `warn` as clean without policy review_input
- **Risk:** an APR-emitted `warn` overall_status flows to a green push.
- **Mitigation:** `overall_status_to_exit_code('warn') == 1`, which is a
  non-zero exit. The aggregator writes the warn reason codes into
  `reason_codes`. Callers (pre-push hook, CI) treat exit≠0 as
  blocking. APR does not silently downgrade warn to pass.
- **Test:** `test_warn_only_passes_when_overall_aggregator_does_not_have_blocks`.
- **Disposition:** resolved.

### MF-11 — APR mutates files or performs repair
- **Risk:** APR could be tempted to auto-rewrite the override map or
  regenerate stale artifacts.
- **Mitigation:** APR only writes under the supplied
  `--phase-output-dir` (default `outputs/agent_pr_precheck/`) and the
  result file (default `outputs/agent_pr_precheck/agent_pr_precheck_result.json`).
  It never opens any file under `docs/`, `contracts/`, `scripts/`, or
  `spectrum_systems/` for writing. Repair belongs to PRL/FRE/CDE/PQX.
- **Test:** `test_apr_only_writes_under_outputs_dir`.
- **Disposition:** resolved.

### MF-12 — APR claims authority owned by CLP / APU / TPA / CDE / SEL / GOV
- **Risk:** APR's docstrings, schema, or per-phase artifact text could
  drift into authority-claim language.
- **Mitigation:** schema description and orchestrator docstring carry
  the standard observation-only declaration. The schema pins
  `authority_scope = "observation_only"` via `const`. A test asserts
  no banned authority verbs appear in APR-owned files.
- **Test:** `test_no_banned_authority_tokens_in_apr_owned_files`.
- **Disposition:** resolved.

### MF-13 — APR emits `present` without artifact refs
- See MF-03 mitigation.
- **Test:** `test_pass_without_output_artifact_refs_is_schema_invalid`.
- **Disposition:** resolved.

### MF-14 — APR emits `missing` / `unknown` / `skipped` / `block` without reason codes
- See MF-03 mitigation.
- **Test:** `test_non_pass_without_reason_codes_is_schema_invalid`.
- **Disposition:** resolved.

### MF-15 — APR schema/example mismatch
- **Mitigation:** `test_canonical_example_validates_against_schema`
  validates the canonical example on every test run.
- **Disposition:** resolved.

### SF-01 — `should_fix`: pin command-strings to CI workflow YAML
- **Risk:** the workflow YAML and APR's subprocess invocations could
  drift.
- **Suggested next slice:** add a contract test that reads
  `.github/workflows/artifact-boundary.yml` and compares the
  `governed-contract-preflight` job's commands to the APR example
  artifact's `command` strings.

### OBS-01 — APR's pre-push hook is opt-in
- **Observation:** users must run `bash scripts/install_hooks.sh` for the
  hook to take effect. This matches existing repo convention. Making it
  mandatory is a separate slice.
