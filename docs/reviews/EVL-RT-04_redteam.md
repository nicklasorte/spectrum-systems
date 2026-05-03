# EVL-RT-04 Red-Team — Require Shard-First Readiness in CLP Pre-PR Evidence

Scope: red-team review of the EVL-RT-04 slice. EVL-RT-04 strengthens
the EVL → CLP pre-PR readiness loop by requiring CLP to consume the
existing `pr_test_shard_first_readiness_observation` artifact (emitted
by `scripts/build_pr_test_shard_first_readiness_observation.py` in
EVL-RT-03) as a required pre-PR readiness check
(`evl_shard_first_readiness`). The slice does not change CI behavior,
does not run pytest, does not mutate test selection, does not weaken
existing required tests or full-suite validation, and does not touch
PRL/F3L runtime, APU PRL evidence policy, the dashboard, or
`.github/workflows/`.

Authority boundary preserved: CLP remains observation-only. The new
check consumes an already-emitted shard-first readiness observation;
it never runs pytest, recomputes selection, or rebuilds the
observation. Canonical ownership of the selector, shard runner,
runtime budget observation, shard-first builder, and any policy
authority remains with the systems declared in
`docs/architecture/system_registry.md`. The CLP runner, helper, and
policy file emit readiness observations only — they never claim
admission, execution closure, eval certification, policy adjudication,
continuation, or final-gate signal authority.

## Authority-safe vocabulary

This document avoids reserved owner-authority verbs and their negated
forms. CLP emits readiness observations, pre-PR observations,
shard-first observations, fallback observations, policy observations,
compliance observations, control inputs, findings, and
recommendations. CLP never approves, certifies, promotes, enforces,
decides, or authorizes anything. The new check name
(`evl_shard_first_readiness`), failure classes
(`evl_shard_first_readiness_*`), reason codes
(`shard_first_status_*`, `fallback_signal_*`,
`pr_test_shard_first_readiness_observation_*`), policy rules, and
schema enum values are scanned for forbidden authority verbs by the
existing non-authority runtime vocabulary tests and by
`tests/test_core_loop_pre_pr_gate_policy.py::test_policy_authority_safe_vocabulary_overall`
plus the existing
`tests/test_core_loop_pre_pr_gate.py::test_clp_does_not_claim_authority`
guard.

## Threat scenarios

### 1. Missing shard-first readiness observation counted as present

Disposition: **closed**.
Mechanism: `consume_shard_first_readiness_observation` reads the
observation file by canonical artifact_type and returns a `block`
check (`failure_class=evl_shard_first_readiness_missing`,
reason_code `pr_test_shard_first_readiness_observation_missing`)
whenever the file is absent. The CLP runner records that block as a
required check; `evaluate_gate` short-circuits the gate to
`gate_status=block` because `evl_shard_first_readiness` is in
`REQUIRED_CHECK_NAMES`. PR-ready handoff is therefore impossible
without an existing artifact on disk.
Tests:
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_when_observation_missing`,
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_missing_required_check_blocks_repo_mutating`,
`tests/test_core_loop_pre_pr_gate_policy.py::test_policy_lists_shard_first_readiness_observation_alias`.

### 2. Unknown status treated as clean

Disposition: **closed**.
Mechanism: `_VALID_SHARD_FIRST_STATUSES` is a closed enum
(`shard_first`, `fallback_justified`, `missing`, `partial`,
`unknown`); any other value coerces to a block check with
`failure_class=evl_shard_first_readiness_invalid`. A literal
`shard_first_status="unknown"` returns a block check with
`failure_class=evl_shard_first_readiness_unknown` and a synthesized
reason code if upstream did not provide one. Both paths set
`evl_shard_first_status="unknown"` in the evidence section so
downstream consumers cannot mistake it for clean.
Tests:
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_on_unknown_status`,
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_on_invalid_artifact`.

### 3. Fallback used without reason codes

Disposition: **closed**.
Mechanism: when the observation reports `fallback_used=true` or
`full_suite_detected=true` without a non-empty
`fallback_justification_ref` AND non-empty `fallback_reason_codes`,
`consume_shard_first_readiness_observation` forces a block check with
`failure_class=evl_shard_first_readiness_fallback_unjustified` and
synthesizes reason codes
(`fallback_signal_without_fallback_justification_ref`,
`fallback_signal_without_fallback_reason_codes`). The schema for the
upstream observation already requires those fields when fallback is
signalled (EVL-RT-02 / EVL-RT-03); CLP's check defends against
schema-violating artifacts that land on disk anyway. CLP also blocks
`shard_first_status=fallback_justified` whose
`fallback_justification_ref` or `fallback_reason_codes` is missing.
Tests:
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_on_fallback_without_justification`,
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_pass_for_fallback_justified_with_refs_and_codes`,
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_warns_on_fallback_codes_outside_allow_list`.

### 4. shard_first status with no shard refs

Disposition: **closed**.
Mechanism: a `shard_first_status="shard_first"` payload with empty
`required_shard_refs` returns a block check
(`failure_class=evl_shard_first_readiness_shard_refs_empty`,
reason_code `shard_first_status_missing_required_shard_refs`). The
upstream schema also rejects this combination (EVL-RT-03), but CLP
cross-checks the same invariant locally so a bypassed validator
cannot silently downgrade the gate.
Tests:
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_on_shard_first_without_refs`,
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_pass_for_shard_first_status_with_refs`.

### 5. PR prose counted as readiness evidence

Disposition: **closed**.
Mechanism: `_read_shard_first_observation` requires a JSON object whose
`artifact_type` equals
`pr_test_shard_first_readiness_observation`. Anything else (free
text, comments, the wrong artifact_type, or non-JSON) returns `None`,
which routes through the invalid-artifact branch and produces a block
check with `failure_class=evl_shard_first_readiness_invalid`. PR
prose, comment threads, and CI success messages cannot satisfy the
artifact-typed contract.
Tests:
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_pr_prose_is_not_evidence`,
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_blocks_on_invalid_artifact`.

### 6. CLP recomputes selection instead of consuming artifact

Disposition: **closed**.
Mechanism: the helper reads the observation JSON only — it never
imports or calls `pr_test_selection.resolve_required_tests`,
`pr_test_selection.build_selection_coverage_record`, or any selector
symbol. A test patches the selector module to raise on call and
asserts the helper still returns `pass`, proving CLP does not run
selection logic for this check.
Tests:
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_does_not_recompute_selection`.

### 7. CLP runs pytest

Disposition: **closed**.
Mechanism: the helper performs only file I/O and JSON parsing on the
observation file. A test monkeypatches `subprocess.run` to raise on
call and asserts the helper still returns `pass`. The CLP runner
script `_check_evl_shard_first_readiness` may invoke the EVL-RT-03
builder only when the policy explicitly opts in
(`invoke_builder_if_missing=true`); the default policy value is
`false` and the canonical builder owner remains EVL. CLP never
invokes pytest for this check.
Tests:
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_does_not_run_pytest`,
`tests/test_core_loop_pre_pr_gate_policy.py::test_policy_shard_first_evidence_section`.

### 8. Measurement layer claims authority

Disposition: **closed**.
Mechanism: the artifact section in the CLP gate result
(`evl_shard_first_evidence`) and the policy section
(`evl_shard_first_readiness_evidence`) are observation-only by
construction: the schema pins `authority_scope` to
`observation_only`, the policy pins `authority_scope` to
`observation_only`, and the policy `must_not_do` list still includes
`claim_review_observation_authority`,
`claim_readiness_evidence_authority`,
`claim_admission_input_authority`,
`claim_execution_input_authority`, and
`claim_continuation_input_authority`. The new policy rules
(`evl_shard_first_readiness_required`,
`evl_shard_first_*_blocks`) are pre-PR observation invariants only;
they do not imply any new authority for CLP. The CLP module
docstring continues to state that CLP does not own admission,
execution closure, eval certification, policy adjudication, control
decision, or final compliance enforcement.
Tests:
`tests/test_core_loop_pre_pr_gate.py::test_authority_scope_remains_observation_only`,
`tests/test_core_loop_pre_pr_gate.py::test_clp_does_not_claim_authority`,
`tests/test_core_loop_pre_pr_gate.py::test_clp_shard_first_preserves_observation_only_authority`,
`tests/test_core_loop_pre_pr_gate_policy.py::test_policy_authority_scope_is_observation_only`,
`tests/test_core_loop_pre_pr_gate_policy.py::test_policy_must_not_do_blocks_authority_overreach`.

### 9. Authority vocabulary regression

Disposition: **closed**.
Mechanism: the existing
`tests/test_core_loop_pre_pr_gate.py::test_clp_does_not_claim_authority`
guard scans the entire CLP artifact JSON for forbidden authority
nouns / verbs (`approval`, `certification`, `promotion`,
`enforcement`, `approved`, `certified`, `promoted`, `enforced`,
`verdict`). The new
`test_policy_authority_safe_vocabulary_overall` guard scans the
policy file. The new check name `evl_shard_first_readiness`,
failure classes (`evl_shard_first_readiness_*`), reason codes
(`shard_first_status_*`, `fallback_signal_*`,
`pr_test_shard_first_readiness_observation_*`), and policy rule
names use authority-safe vocabulary throughout. The non-authority
runtime vocabulary suite continues to pass.
Tests:
`tests/test_core_loop_pre_pr_gate.py::test_clp_does_not_claim_authority`,
`tests/test_core_loop_pre_pr_gate_policy.py::test_policy_authority_safe_vocabulary_overall`,
`tests/test_non_authority_runtime_vocabulary.py`.

## Residual risks

- The CLP runner only invokes the EVL-RT-03 builder when the policy
  flag `invoke_builder_if_missing=true` is set. The default is
  `false`, so a missing artifact fails closed via the missing-file
  branch. This residual is intentional: CLP should never silently
  rebuild upstream evidence in normal operation; recovery belongs to
  PRL/FRE/CDE/PQX or the upstream EVL-RT-03 builder run.
- The allow-list path
  (`allowed_fallback_reason_codes`) downgrades a `fallback_justified`
  observation with non-allow-listed codes to a `warn` rather than a
  block. CLP-02 policy
  (`clp_warn_requires_explicit_allow=true`) and the existing CLP-02
  policy evaluator
  (`spectrum_systems/modules/runtime/core_loop_pre_pr_gate_policy.py`)
  still surface the warn upstream as `not_ready` whenever the warn
  reason codes are not in `allowed_warn_reason_codes`. The default
  `allowed_warn_reason_codes` list is empty, so the residual is closed
  unless TPA expressly opts in.

## References

- `spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py`
- `scripts/run_core_loop_pre_pr_gate.py`
- `contracts/schemas/core_loop_pre_pr_gate_result.schema.json`
- `contracts/examples/core_loop_pre_pr_gate_result.example.json`
- `docs/governance/core_loop_pre_pr_gate_policy.json`
- `contracts/schemas/pr_test_shard_first_readiness_observation.schema.json`
- `scripts/build_pr_test_shard_first_readiness_observation.py`
- `tests/test_core_loop_pre_pr_gate.py`
- `tests/test_core_loop_pre_pr_gate_policy.py`
- `docs/reviews/EVL-RT-03_redteam.md`
