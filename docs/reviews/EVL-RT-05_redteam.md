# EVL-RT-05 Red-Team — Wire Shard-First Readiness Evidence Into APU PR-Update Readiness

Scope: red-team review of the EVL-RT-05 slice. EVL-RT-05 strengthens
the EVL → CLP → APU readiness loop by wiring the existing
`pr_test_shard_first_readiness_observation` artifact (emitted by
`scripts/build_pr_test_shard_first_readiness_observation.py` in
EVL-RT-03 and consumed by CLP in EVL-RT-04) into APU's
`agent_pr_update_ready_result`. APU now surfaces shard-first status,
shard-first evidence status, fallback status, and reason codes
directly on the PR-update readiness observation. The slice does not
change CI behavior, does not run pytest, does not mutate test
selection, does not duplicate selector logic, does not weaken
existing required tests, full-suite validation, PRL/F3L runtime, or
the dashboard, and does not touch `.github/workflows/`.

Authority boundary preserved: APU remains observation-only. APU
consumes the shard-first observation directly when supplied;
otherwise it falls back to the `evl_shard_first_evidence` block
recorded by CLP. APU never runs pytest, recomputes shard selection,
or rebuilds the observation. Canonical authority for selection,
shard execution, shard mapping, runtime budget observation,
shard-first builder, and any policy decisions remains with the
systems declared in `docs/architecture/system_registry.md`. APU emits
PR-update readiness observations only — it never claims admission,
execution closure, evaluation evidence, policy, continuation, or
final-gate signal authority.

## Authority-safe vocabulary

This document avoids reserved owner-authority verbs and their negated
forms. APU emits PR-update readiness observations, shard-first
observations, fallback observations, EVL evidence observations,
policy observations, control inputs, findings, and recommendations.
APU never approves, certifies, promotes, enforces, decides, or
authorizes anything. The new field names (`shard_first_status`,
`shard_first_evidence_status`, `shard_first_reason_codes`,
`shard_first_fallback_used`, `shard_first_full_suite_detected`,
`shard_first_fallback_reason_codes`,
`shard_first_required_for_repo_mutating`,
`shard_first_readiness_ref`), policy rule names
(`repo_mutating_requires_shard_first_evidence`,
`shard_first_fallback_requires_reason_codes`,
`shard_first_full_suite_requires_reason_codes`,
`shard_first_pr_body_prose_is_not_evidence`), and block reason codes
(`shard_first_evidence_*`, `shard_first_status_*`,
`shard_first_fallback_*`,
`shard_first_readiness_observation_*`,
`shard_first_full_suite_detected_*`) use authority-safe vocabulary.
The `tests/test_check_agent_pr_update_ready.py` suite scans the APU
artifact JSON for forbidden owner-authority tokens via
`test_apu_artifact_preserves_authority_safe_vocabulary` and the
existing `test_apu_artifact_does_not_claim_owner_authority` /
`test_example_does_not_claim_owner_authority` guards.

## Threat scenarios

### 1. Missing shard-first evidence treated as present

Disposition: **closed**.
Mechanism: `_evaluate_shard_first_evidence` in
`spectrum_systems/modules/runtime/agent_pr_update_policy.py` returns
`shard_first_evidence_status="missing"` and a synthesized reason
code (`shard_first_readiness_observation_missing`) when neither a
direct `pr_test_shard_first_readiness_observation` artifact nor a
CLP-recorded `evl_shard_first_evidence` block is supplied. When
`repo_mutating=true`, `evaluate_pr_update_ready` adds
`shard_first_evidence_missing_for_repo_mutating` to `reason_codes`
and short-circuits readiness to `not_ready`. The schema marks
`shard_first_evidence_status` as required and rejects an artifact
that claims `shard_first_evidence_status="present"` without a
`shard_first_readiness_ref`. PR-update readiness handoff is
therefore impossible without an artifact-backed shard-first
observation.
Tests:
`tests/test_check_agent_pr_update_ready.py::test_repo_mutating_missing_shard_first_evidence_yields_not_ready`,
`tests/test_check_agent_pr_update_ready.py::test_apu_artifact_validates_with_shard_first_fields`.

### 2. Unknown shard-first status treated as clean

Disposition: **closed**.
Mechanism: `_evaluate_shard_first_evidence` maps
`shard_first_status="unknown"` to
`shard_first_evidence_status="unknown"`, synthesizes
`shard_first_status_unknown_without_reason_codes` if no upstream
reason code is present, and lists
`shard_first_status_unknown` in the blocking reasons. When
`repo_mutating=true`, `evaluate_pr_update_ready` lifts the blocking
reasons into `reason_codes` and adds
`shard_first_evidence_unknown_for_repo_mutating`, forcing
readiness to `not_ready`. An invalid `shard_first_status` value is
coerced to `unknown` with `shard_first_readiness_observation_invalid`
so a typo, schema-violating value, or stale artifact cannot pass as
clean.
Tests:
`tests/test_check_agent_pr_update_ready.py::test_repo_mutating_unknown_shard_first_evidence_yields_not_ready`,
`tests/test_check_agent_pr_update_ready.py::test_repo_mutating_missing_status_shard_first_evidence_yields_not_ready`,
`tests/test_check_agent_pr_update_ready.py::test_repo_mutating_partial_shard_first_evidence_yields_not_ready`.

### 3. Fallback / full-suite state without reason codes

Disposition: **closed**.
Mechanism: `_evaluate_shard_first_evidence` adds
`shard_first_fallback_used_without_reason_codes` and
`shard_first_full_suite_detected_without_reason_codes` to the
shard-first reason codes when `fallback_used=true` or
`full_suite_detected=true` is observed without a non-empty
`fallback_reason_codes` list, and downgrades a shard-first evidence
status of `present` to `partial` so the shape invariant cannot be
silently ignored. `evaluate_pr_update_ready` lifts those reason
codes into the top-level `reason_codes` list whenever
`repo_mutating=true`, and the agent_pr_update_ready_result schema
also rejects `shard_first_fallback_used=true` or
`shard_first_full_suite_detected=true` without at least one
`shard_first_fallback_reason_codes` entry. Two complementary
fail-closed checks (logic + schema) defend the same invariant.
Tests:
`tests/test_check_agent_pr_update_ready.py::test_repo_mutating_fallback_used_without_reason_codes_yields_not_ready`,
`tests/test_check_agent_pr_update_ready.py::test_repo_mutating_full_suite_detected_without_reason_codes_yields_not_ready`.

### 4. PR prose counted as shard-first evidence

Disposition: **closed**.
Mechanism: `load_shard_first_readiness_observation` requires a JSON
object whose `artifact_type` equals
`pr_test_shard_first_readiness_observation`. Anything else (free
text, comments, the wrong artifact_type, non-JSON, or a partial
payload) returns `None`, which routes through the missing-evidence
branch and yields
`shard_first_readiness_observation_missing` in the shard-first
reason codes. Combined with
`repo_mutating_requires_shard_first_evidence=true`, PR-body prose
cannot satisfy the artifact-typed contract and APU surfaces
`not_ready`. The policy explicitly lists
`shard_first_pr_body_prose_is_not_evidence` in `rules` and continues
to list `treat_pr_body_as_evidence` in `must_not_do`.
Tests:
`tests/test_check_agent_pr_update_ready.py::test_pr_body_prose_cannot_substitute_for_shard_first_evidence`.

### 5. APU runs pytest

Disposition: **closed**.
Mechanism: `_evaluate_shard_first_evidence` performs only dict
inspection and never calls `subprocess.run`, `os.system`,
`subprocess.Popen`, or any pytest entrypoint. The new tests patch
`subprocess.run` to fail when invoked with a pytest-bearing argv and
exercise the shard-first path end-to-end; APU continues to surface
`ready` so a pytest invocation would have crashed the test.
Tests:
`tests/test_check_agent_pr_update_ready.py::test_apu_does_not_run_pytest`.

### 6. APU recomputes selector state

Disposition: **closed**.
Mechanism: APU never imports `pr_test_selection`,
`build_pr_test_shard_first_readiness_observation`,
`pytest_pr_selection`, or any selector symbol. The shard-first
helper only reads dict fields produced by EVL/CLP. A direct test
supplies custom `required_shard_refs` and asserts APU surfaces
exactly that list verbatim, proving APU does not re-derive shard
selection.
Tests:
`tests/test_check_agent_pr_update_ready.py::test_apu_does_not_recompute_shard_selection`,
`tests/test_check_agent_pr_update_ready.py::test_repo_mutating_shard_first_status_with_refs_allows_ready`.

### 7. Measurement layer claims authority

Disposition: **closed**.
Mechanism: the agent_pr_update_ready_result artifact pins
`authority_scope` to `observation_only` (schema `const`) and the
policy still pins its `authority_scope` to `observation_only`. The
new policy rules
(`repo_mutating_requires_shard_first_evidence`,
`shard_first_fallback_requires_reason_codes`,
`shard_first_full_suite_requires_reason_codes`,
`shard_first_pr_body_prose_is_not_evidence`) and policy block reason
codes are PR-update readiness observation invariants; they do not
imply any new authority for APU. The policy's `must_not_do` list
continues to forbid `claim_admission_authority`,
`claim_execution_authority`, `claim_eval_authority`,
`claim_policy_authority`, `claim_continuation_authority`,
`claim_final_gate_authority`, `claim_lineage_authority`,
`claim_replay_authority`, and `treat_pr_body_as_evidence`. EVL,
CLP, and the canonical owners declared in
`docs/architecture/system_registry.md` retain selection, shard
execution, shard mapping, eval certification, and final-gate
authority.
Tests:
`tests/test_check_agent_pr_update_ready.py::test_apu_artifact_authority_scope_observation_only`,
`tests/test_check_agent_pr_update_ready.py::test_apu_artifact_does_not_claim_owner_authority`.

### 8. Authority vocabulary regression

Disposition: **closed**.
Mechanism: the new shard-first field names, status enum values,
reason codes, and policy rule names use authority-safe vocabulary
throughout. The new
`test_apu_artifact_preserves_authority_safe_vocabulary` test scans
the entire APU artifact JSON for forbidden owner-authority tokens
(`approved`, `certified`, `promoted`, `enforced`, `approval`,
`certification`, `promotion`, `enforcement`, `adjudication`,
`authorization`, `verdict`). The existing
`test_apu_artifact_does_not_claim_owner_authority`,
`test_example_does_not_claim_owner_authority`, and
`test_apu_artifact_negated_authority_phrases_absent_from_pr_section`
guards continue to scan the artifact and example for both bare and
negated forms. The non-authority runtime vocabulary suite continues
to pass.
Tests:
`tests/test_check_agent_pr_update_ready.py::test_apu_artifact_preserves_authority_safe_vocabulary`,
`tests/test_check_agent_pr_update_ready.py::test_apu_artifact_does_not_claim_owner_authority`,
`tests/test_check_agent_pr_update_ready.py::test_example_does_not_claim_owner_authority`,
`tests/test_check_agent_pr_update_ready.py::test_apu_artifact_negated_authority_phrases_absent_from_pr_section`.

### 9. Evidence hash omits shard-first refs

Disposition: **closed**.
Mechanism: the `evidence_hash_input` dict in
`evaluate_pr_update_ready` now includes a `shard_first_evidence`
sub-dict with the observation ref, status, evidence status,
required shard refs, fallback signals, fallback justification ref,
fallback reason codes, shard-first reason codes, and source
(`direct` / `clp` / `none`). Two evaluations that differ only in
shard-first evidence (different `required_shard_refs`) produce
different `evidence_hash` values. The shard-first observation ref,
fallback justification ref, and CLP-derived shard-first ref are also
appended to `source_artifact_refs` on the artifact, so replay and
lineage consumers can locate the source artifact directly.
Tests:
`tests/test_check_agent_pr_update_ready.py::test_apu_artifact_includes_shard_first_refs_in_source_artifact_refs_and_hash`.

## Residual risks

- APU treats a CLP-recorded `evl_shard_first_evidence` block as
  acceptable when no direct artifact is supplied. CLP records the
  block from the upstream observation in EVL-RT-04, and CLP's own
  consumer enforces shape invariants (missing artifact, invalid
  artifact_type, fallback without reason codes, shard_first without
  refs). The residual is closed because CLP's evidence shape is
  validated upstream and APU still applies the same fallback /
  full-suite invariants on the CLP-recorded block. A
  `shard_first_source` field on the evidence-hash input distinguishes
  direct vs. CLP-recorded observations so replay can detect a missing
  upstream artifact.
- The schema permits `shard_first_evidence_status="present"` only
  when `shard_first_readiness_ref` is non-empty, but does not require
  the ref to point to a file on disk. Replay and downstream consumers
  resolve the ref against the workspace and surface a missing-file
  failure outside APU. The residual is intentional: APU is
  observation-only and does not own filesystem access for downstream
  consumers.

## References

- `spectrum_systems/modules/runtime/agent_pr_update_policy.py`
- `scripts/check_agent_pr_update_ready.py`
- `contracts/schemas/agent_pr_update_ready_result.schema.json`
- `contracts/examples/agent_pr_update_ready_result.example.json`
- `docs/governance/agent_pr_update_policy.json`
- `tests/test_check_agent_pr_update_ready.py`
- `contracts/schemas/pr_test_shard_first_readiness_observation.schema.json`
- `scripts/build_pr_test_shard_first_readiness_observation.py`
- `spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py`
- `docs/reviews/EVL-RT-04_redteam.md`
- `docs/reviews/EVL-RT-03_redteam.md`
