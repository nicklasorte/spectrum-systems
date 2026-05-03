# EVL-RT-05 Fix Actions — Wire Shard-First Readiness Evidence Into APU PR-Update Readiness

This document records the must_fix findings closed by the EVL-RT-05
slice. Each entry names the finding, the file changed, the test
added or updated, the command run, and the disposition.

## Finding F-EVL-RT-05-01 — Shard-first readiness evidence not surfaced by APU

- finding ID: `F-EVL-RT-05-01`
- description: EVL-RT-04 wired shard-first readiness into CLP, but
  APU surfaced only the generic CLP gate status. APU's
  `agent_pr_update_ready_result` did not carry the shard-first
  observation ref, status, fallback state, or reason codes. A
  CLP-derived block whose root cause was a missing or fallback-only
  shard-first observation could therefore appear on APU's PR-update
  readiness artifact without an EVL-rooted explanation, weakening
  diagnosis and replay.
- files changed:
  - `spectrum_systems/modules/runtime/agent_pr_update_policy.py`
  - `scripts/check_agent_pr_update_ready.py`
  - `contracts/schemas/agent_pr_update_ready_result.schema.json`
  - `contracts/examples/agent_pr_update_ready_result.example.json`
  - `docs/governance/agent_pr_update_policy.json`
- tests added:
  - `tests/test_check_agent_pr_update_ready.py::test_repo_mutating_missing_shard_first_evidence_yields_not_ready`
  - `tests/test_check_agent_pr_update_ready.py::test_repo_mutating_partial_shard_first_evidence_yields_not_ready`
  - `tests/test_check_agent_pr_update_ready.py::test_repo_mutating_unknown_shard_first_evidence_yields_not_ready`
  - `tests/test_check_agent_pr_update_ready.py::test_repo_mutating_missing_status_shard_first_evidence_yields_not_ready`
  - `tests/test_check_agent_pr_update_ready.py::test_repo_mutating_shard_first_status_with_refs_allows_ready`
  - `tests/test_check_agent_pr_update_ready.py::test_clp_recorded_shard_first_evidence_is_observed_when_no_direct_artifact`
  - `tests/test_check_agent_pr_update_ready.py::test_apu_artifact_validates_with_shard_first_fields`
- command run:
  `python -m pytest tests/test_check_agent_pr_update_ready.py -q`
- disposition: **closed**. APU now consumes the shard-first readiness
  observation directly when supplied; otherwise it falls back to the
  `evl_shard_first_evidence` block recorded by CLP. APU surfaces
  `shard_first_status`, `shard_first_evidence_status`,
  `shard_first_reason_codes`, `shard_first_fallback_used`,
  `shard_first_full_suite_detected`,
  `shard_first_fallback_reason_codes`,
  `shard_first_required_for_repo_mutating`, and
  `shard_first_readiness_ref` on `agent_pr_update_ready_result`.
  Repo-mutating slices with missing, partial, or unknown shard-first
  evidence surface as `not_ready` with artifact-backed reason codes.

## Finding F-EVL-RT-05-02 — Fallback / full-suite state could be silent

- finding ID: `F-EVL-RT-05-02`
- description: A shard-first observation could report
  `fallback_used=true` or `full_suite_detected=true` without
  populating `fallback_reason_codes`. APU previously had no policy
  rule rejecting this combination, so a silent fallback or full-suite
  run could pass the PR-update readiness handoff.
- files changed:
  - `spectrum_systems/modules/runtime/agent_pr_update_policy.py`
  - `contracts/schemas/agent_pr_update_ready_result.schema.json`
  - `docs/governance/agent_pr_update_policy.json`
- tests added:
  - `tests/test_check_agent_pr_update_ready.py::test_repo_mutating_fallback_used_without_reason_codes_yields_not_ready`
  - `tests/test_check_agent_pr_update_ready.py::test_repo_mutating_full_suite_detected_without_reason_codes_yields_not_ready`
- command run:
  `python -m pytest tests/test_check_agent_pr_update_ready.py -q`
- disposition: **closed**. APU surfaces
  `shard_first_fallback_used_without_reason_codes` and
  `shard_first_full_suite_detected_without_reason_codes` reason
  codes whenever the shape invariants are violated. The schema
  rejects `shard_first_fallback_used=true` and
  `shard_first_full_suite_detected=true` without at least one
  `shard_first_fallback_reason_codes` entry. Two complementary
  fail-closed checks (logic + schema) defend the same invariant.

## Finding F-EVL-RT-05-03 — PR prose could substitute for shard-first artifact

- finding ID: `F-EVL-RT-05-03`
- description: Free-text JSON or a wrong-typed artifact at the
  shard-first readiness path could be mistaken for a valid
  observation, weakening the artifact-backed evidence invariant.
- files changed:
  - `spectrum_systems/modules/runtime/agent_pr_update_policy.py`
- tests added:
  - `tests/test_check_agent_pr_update_ready.py::test_pr_body_prose_cannot_substitute_for_shard_first_evidence`
- command run:
  `python -m pytest tests/test_check_agent_pr_update_ready.py -q`
- disposition: **closed**. The
  `load_shard_first_readiness_observation` loader requires JSON whose
  `artifact_type` equals
  `pr_test_shard_first_readiness_observation`; anything else returns
  `None`, which routes through the missing-evidence branch. The
  policy lists `shard_first_pr_body_prose_is_not_evidence` in
  `rules` and continues to list `treat_pr_body_as_evidence` in
  `must_not_do`.

## Finding F-EVL-RT-05-04 — APU could run pytest or recompute selection

- finding ID: `F-EVL-RT-05-04`
- description: A new shard-first evidence path could have introduced
  a code path that re-derives selection or invokes pytest, violating
  APU's observation-only authority scope.
- files changed:
  - `spectrum_systems/modules/runtime/agent_pr_update_policy.py`
  - `scripts/check_agent_pr_update_ready.py`
- tests added:
  - `tests/test_check_agent_pr_update_ready.py::test_apu_does_not_run_pytest`
  - `tests/test_check_agent_pr_update_ready.py::test_apu_does_not_recompute_shard_selection`
- command run:
  `python -m pytest tests/test_check_agent_pr_update_ready.py -q`
- disposition: **closed**. The shard-first helper performs only
  dict inspection. A test patches `subprocess.run` to fail when
  invoked with a pytest argv and exercises the shard-first path
  end-to-end. Another test supplies custom `required_shard_refs` and
  asserts APU surfaces exactly that list verbatim.

## Finding F-EVL-RT-05-05 — Authority-shape preservation

- finding ID: `F-EVL-RT-05-05`
- description: Adding shard-first fields to the APU artifact and
  policy could have leaked reserved owner-authority verbs into APU
  code, schema, policy, runner, or tests, contrary to APU's
  observation-only scope.
- files changed:
  - `spectrum_systems/modules/runtime/agent_pr_update_policy.py`
  - `scripts/check_agent_pr_update_ready.py`
  - `contracts/schemas/agent_pr_update_ready_result.schema.json`
  - `contracts/examples/agent_pr_update_ready_result.example.json`
  - `docs/governance/agent_pr_update_policy.json`
- tests added:
  - `tests/test_check_agent_pr_update_ready.py::test_apu_artifact_preserves_authority_safe_vocabulary`
- command run:
  `python -m pytest tests/test_check_agent_pr_update_ready.py -q`
- disposition: **closed**. New field names, status enum values,
  reason codes, schema enum values, policy rule names, and policy
  notes use authority-safe vocabulary. The APU artifact remains
  `authority_scope=observation_only`. The existing
  `test_apu_artifact_does_not_claim_owner_authority`,
  `test_example_does_not_claim_owner_authority`, and
  `test_apu_artifact_negated_authority_phrases_absent_from_pr_section`
  guards continue to pass.

## Finding F-EVL-RT-05-06 — Evidence hash and source artifact refs omitted shard-first evidence

- finding ID: `F-EVL-RT-05-06`
- description: APU's evidence hash and `source_artifact_refs`
  previously did not include the shard-first observation ref or
  fields. Two evaluations differing only in shard-first evidence
  could share the same `evidence_hash`, weakening replay and
  lineage.
- files changed:
  - `spectrum_systems/modules/runtime/agent_pr_update_policy.py`
- tests added:
  - `tests/test_check_agent_pr_update_ready.py::test_apu_artifact_includes_shard_first_refs_in_source_artifact_refs_and_hash`
- command run:
  `python -m pytest tests/test_check_agent_pr_update_ready.py -q`
- disposition: **closed**. The `evidence_hash_input` dict now
  includes a `shard_first_evidence` sub-dict with the observation
  ref, status, evidence status, required shard refs, fallback
  signals, fallback justification ref, fallback reason codes,
  shard-first reason codes, and source. The shard-first observation
  ref, fallback justification ref, and CLP-derived shard-first ref
  are appended to `source_artifact_refs` on the artifact.
