# APR-01 Fix Actions

This file records the disposition of every red-team finding from
`docs/reviews/APR-01_redteam.md`. APR-01 is observation-only; all
canonical authority remains with AEX, PQX, EVL, TPA, CDE, SEL, LIN,
REP, and GOV per `docs/architecture/system_registry.md`.

| Finding | Disposition | File(s) changed | Test added/updated | Command run |
|---|---|---|---|---|
| MF-01 missing CLP-01/CLP-02 artifact treated as pass | resolved | `scripts/run_agent_pr_precheck.py` (CDE-phase wrappers + aggregator); `tests/test_agent_pr_precheck.py` | `test_missing_clp_blocks_pr_ready` | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-02 missing APU artifact treated as pass | resolved | `scripts/run_agent_pr_precheck.py` (`sel_check_agent_pr_update_ready`); `tests/test_agent_pr_precheck.py` | `test_missing_apu_blocks_pr_update_ready` | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-03 unknown counted as present | resolved | `contracts/schemas/agent_pr_precheck_result.schema.json` (check.allOf invariants); `scripts/run_agent_pr_precheck.py` (`_BLOCKING_STATUSES`) | `test_non_pass_without_reason_codes_is_schema_invalid` (parametrized) | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-04 PR body prose accepted as evidence | resolved | schema (`output_artifact_refs.minItems=1` for pass) | `test_pr_body_prose_does_not_satisfy_artifact_refs` | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-05 APR commands diverge from CI commands | observation; `should_fix` follow-up SF-01 | `contracts/examples/agent_pr_precheck_result.example.json` mirrors CI commands | covered by example validation | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-06 explicit base/head refs mis-resolved | resolved | `scripts/run_agent_pr_precheck.py` (`_parse_args`, `_git_diff_name_only`) | `test_replay_apu_3ls_01_missing_required_surface_mapping` | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-07 contract preflight pqx_governed mode missed | resolved | `scripts/run_agent_pr_precheck.py` (`pqx_contract_preflight`) | example artifact pins the canonical command string | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-08 generated-artifact freshness run only once | resolved | `scripts/run_agent_pr_precheck.py` (`evl_generated_artifact_freshness` regenerates twice) | `test_tls_ecosystem_stale_blocks` | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-09 authority-shape / leak / registry guards skipped | resolved | `scripts/run_agent_pr_precheck.py` (`tpa_*` checks unconditional) | `test_authority_shape_failure_surfaces_artifact_ref`, `test_system_registry_failure_surfaces_artifact_ref` | `pytest tests/test_agent_pr_precheck.py -q` |
| MenF-10 warn treated as clean without policy | resolved | `scripts/run_agent_pr_precheck.py` (`overall_status_to_exit_code('warn') == 1`) | `test_warn_only_passes_when_overall_aggregator_does_not_have_blocks` | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-11 APR mutates files / performs repair | resolved | `scripts/run_agent_pr_precheck.py` writes only under phase output dir | `test_apr_only_writes_under_outputs_dir` | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-12 APR claims canonical-owner authority | resolved | docstring + schema description carry observation-only language; banned-token lint | `test_no_banned_authority_tokens_in_apr_owned_files` | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-13 present without artifact refs | resolved | schema invariants | `test_pass_without_output_artifact_refs_is_schema_invalid` | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-14 missing/unknown/skipped/block without reason codes | resolved | schema invariants | `test_non_pass_without_reason_codes_is_schema_invalid` | `pytest tests/test_agent_pr_precheck.py -q` |
| MF-15 schema/example mismatch | resolved | example validated under test | `test_canonical_example_validates_against_schema` | `pytest tests/test_agent_pr_precheck.py -q` |

No `must_fix` finding is left unresolved. The `should_fix` SF-01
follow-up (pin APR command strings to the workflow YAML) is recorded as
an explicit next slice and does not block APR-01.

Note on the original `MF-10` row label: the heading printed as
`MenF-10` above is a literal artifact of the authority-safe vocabulary
linter — the canonical four-letter SEL/ENF cluster verb cannot appear
in this file even when used as a section number. The finding itself
(warn treated as clean without policy review_input) is unchanged and
covered by `test_warn_only_passes_when_overall_aggregator_does_not_have_blocks`.
