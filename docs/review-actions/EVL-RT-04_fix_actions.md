# EVL-RT-04 Fix Actions — Require Shard-First Readiness in CLP

This document records the must_fix findings closed by the EVL-RT-04
slice. Each entry names the finding, the file changed, the
test added or updated, the command run, and the disposition.

## Finding F-EVL-RT-04-01 — Shard-first readiness observation not consumed by CLP

- finding ID: `F-EVL-RT-04-01`
- description: Shard-first PR readiness was emitted as an observation
  by EVL-RT-03 but was not required by the CLP pre-PR gate. A
  repo-mutating change could therefore appear pre-PR ready without
  proving the upstream shard-first readiness observation was
  consumed.
- files changed:
  - `spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py`
  - `scripts/run_core_loop_pre_pr_gate.py`
  - `contracts/schemas/core_loop_pre_pr_gate_result.schema.json`
  - `contracts/examples/core_loop_pre_pr_gate_result.example.json`
  - `docs/governance/core_loop_pre_pr_gate_policy.json`
- tests added:
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_when_observation_missing`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_pass_for_shard_first_status_with_refs`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_pass_for_fallback_justified_with_refs_and_codes`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_warns_on_fallback_codes_outside_allow_list`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_on_missing_status`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_on_partial_status`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_on_unknown_status`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_on_fallback_without_justification`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_on_shard_first_without_refs`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_on_invalid_artifact`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_pr_prose_is_not_evidence`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_does_not_run_pytest`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_does_not_recompute_selection`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_preserves_observation_only_authority`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_existing_required_checks_still_work`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_missing_required_check_blocks_repo_mutating`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_evidence_field_optional_in_schema`
  - `tests/test_core_loop_pre_pr_gate_policy.py::test_policy_lists_shard_first_readiness_observation_alias`
  - `tests/test_core_loop_pre_pr_gate_policy.py::test_policy_block_codes_cover_shard_first_failures`
  - `tests/test_core_loop_pre_pr_gate_policy.py::test_policy_rules_include_shard_first_invariants`
  - `tests/test_core_loop_pre_pr_gate_policy.py::test_policy_shard_first_evidence_section`
  - `tests/test_core_loop_pre_pr_gate_policy.py::test_policy_authority_safe_vocabulary_overall`
- command run:
  `python -m pytest tests/test_core_loop_pre_pr_gate.py
  tests/test_core_loop_pre_pr_gate_policy.py -q`
- disposition: **closed**. CLP now requires the shard-first readiness
  observation as a pre-PR check; missing, invalid, partial, unknown,
  or unjustified-fallback states block pre-PR readiness with
  artifact-backed reason codes.

## Finding F-EVL-RT-04-02 — PR prose could substitute for shard-first artifact

- finding ID: `F-EVL-RT-04-02`
- description: A free-text file at the observation path, or a JSON
  payload with the wrong `artifact_type`, could have been mistaken
  for a valid shard-first readiness observation.
- files changed:
  - `spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py`
- tests added:
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_pr_prose_is_not_evidence`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_on_invalid_artifact`
- command run:
  `python -m pytest tests/test_core_loop_pre_pr_gate.py -q`
- disposition: **closed**. The reader requires JSON whose
  `artifact_type` equals `pr_test_shard_first_readiness_observation`;
  anything else routes to the invalid-artifact branch and produces a
  block check (`failure_class=evl_shard_first_readiness_invalid`).

## Finding F-EVL-RT-04-03 — Authority-shape preservation

- finding ID: `F-EVL-RT-04-03`
- description: Adding a new CLP check could have leaked reserved
  owner-authority verbs into CLP code, schema, policy, runner, or
  tests, contrary to CLP's observation-only scope. The canonical
  reserved-vocabulary list lives in
  `contracts/governance/authority_shape_vocabulary.json` and is
  scanned by `scripts/run_authority_shape_preflight.py`.
- files changed:
  - `spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py`
  - `scripts/run_core_loop_pre_pr_gate.py`
  - `contracts/schemas/core_loop_pre_pr_gate_result.schema.json`
  - `contracts/examples/core_loop_pre_pr_gate_result.example.json`
  - `docs/governance/core_loop_pre_pr_gate_policy.json`
- tests added:
  - `tests/test_core_loop_pre_pr_gate.py::test_authority_scope_remains_observation_only`
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_does_not_claim_authority` (existing — guards new evidence section)
  - `tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_preserves_observation_only_authority`
  - `tests/test_core_loop_pre_pr_gate_policy.py::test_policy_authority_safe_vocabulary_overall`
- command run:
  `python -m pytest tests/test_core_loop_pre_pr_gate.py
  tests/test_core_loop_pre_pr_gate_policy.py
  tests/test_non_authority_runtime_vocabulary.py -q`
- disposition: **closed**. New check name, failure classes, reason
  codes, schema enum values, policy rule names, and policy notes use
  authority-safe vocabulary. The CLP artifact remains
  `authority_scope=observation_only` and the policy retains its
  `must_not_do` authority-claim guards.
