# M3L-03 Red-Team Review — Gate / Shard Parity Measurement

Categories: `must_fix` (blocks the PR), `should_fix` (open follow-up
before the next dependent slice), `observation` (informational).

M3L-03 is observation-only. It surfaces shard parity measurement
observations only. It introduces no new gate, no readiness signal, no
admission, execution, eval, policy, control, or final-gate authority.
Canonical authority remains with AEX (admission), PQX (bounded execution
closure), EVL (eval evidence), TPA (policy/scope), CDE
(continuation/closure), SEL (final gate signal), LIN (lineage), REP
(replay), and GOV per `docs/architecture/system_registry.md`. Each
finding below names the canonical owner whose authority the finding
pretends to claim, and the mitigation that keeps M3L-03 inside its
measurement envelope.

## Findings

### MF-01 — Missing shard artifacts incorrectly treated as aligned
- **Risk:** the builder receives an APR/CLP/summary that all reference
  the canonical shard refs, but the shard files have been deleted or
  never existed on disk; the builder reports `parity_status=aligned`
  while the EVL evidence is gone.
- **Owner pretended:** EVL (eval evidence presence).
- **Mitigation:** `find_missing_artifact_refs` walks every ref claimed
  by APR, CLP, or the summary and checks on-disk presence under the
  repo root. Any ref that does not resolve to a file becomes a
  `shard_artifact_missing_on_disk` finding and forces
  `parity_status=partial` with a reason code. The schema's `aligned`
  branch additionally requires `missing_artifact_refs` and
  `mismatch_findings` to be empty.
- **Test:** `test_partial_refs_missing_on_disk` materialises only a
  subset of the canonical refs and asserts `partial` with the missing
  refs surfaced and `shard_artifact_missing_on_disk` in
  `reason_codes`.
- **Disposition:** resolved.

### MF-02 — Stale shard artifacts treated as current
- **Risk:** the on-disk shard files exist but are from a previous run
  (different base/head), so APR/CLP/summary all "agree" on stale data.
- **Owner pretended:** EVL (recency of eval evidence).
- **Mitigation:** parity is measurement only — it never claims that
  artifacts are current. The record records `base_ref` and `head_ref`
  verbatim from CLI args; downstream consumers (APR/CLP) are the
  systems that fail closed on stale artifacts. The
  `apr_clp_shard_ref_mismatch` finding catches the case where APR and
  CLP each consumed a different shard set, which is the most common
  staleness symptom. The `pr_test_shard_runner_failed` and
  `pr_test_shard_summary_stale_or_untrusted` reason codes already
  emitted by APR's `evl_pr_test_shards` check propagate into APR's
  `selected_test_refs` blob, where the parity builder reads them.
- **Test:** `test_apr_clp_ref_set_mismatch` asserts the diff between
  APR's and CLP's shard ref sets becomes a drift finding.
- **Disposition:** observation; staleness detection beyond ref-set
  diff is owned by APR/CLP. M3L-03 surfaces it but does not redefine
  it.

### MF-03 — APR and CLP referencing different artifacts but not detected
- **Risk:** APR consumes shard outputs from one run, CLP consumes the
  same shard outputs from a different run; both report `pass` and the
  parity record marks them aligned.
- **Owner pretended:** EVL (cross-system evidence consistency).
- **Mitigation:** `detect_parity` computes
  `apr_clp_mismatch = (apr_shard_ref_set != clp_shard_ref_set)`
  whenever both ref sets are non-empty. Any difference produces an
  `apr_clp_shard_ref_mismatch` finding plus the matching reason code
  and downgrades parity to `drift`. The schema's `aligned` branch
  forbids `apr_clp_mismatch=true`.
- **Test:** `test_apr_clp_ref_set_mismatch`.
- **Disposition:** resolved.

### MF-04 — GitHub shard failure not flagged when APR/CLP report pass
- **Risk:** the GitHub-driven shard summary reports `block` (because a
  required shard failed), but APR's local shard re-run reported pass;
  the parity builder treats APR's pass as authoritative and hides the
  GitHub failure.
- **Owner pretended:** EVL (CI fail-closed signal).
- **Mitigation:** `github_escape = (apr_status == "pass" and
  github_shard_status in {fail, block, missing, unknown})`. The same
  rule applies to CLP via `clp_github_mismatch`. Both flips force
  `parity_status=drift`, surface the matching mismatch finding, and
  are forbidden by the schema's `aligned` branch.
- **Test:** `test_apr_pass_github_fail_drift_with_github_escape`,
  `test_clp_pass_github_fail_drift_with_clp_github_mismatch`.
- **Disposition:** resolved.

### MF-05 — `unknown` treated as aligned
- **Risk:** missing inputs produce `unknown` statuses that are silently
  rolled up as `aligned`.
- **Owner pretended:** GOV (artifact existence guarantees).
- **Mitigation:** `detect_parity` early-exits to `parity_status=unknown`
  whenever `summary_present`, `apr_present`, or `clp_present` is false.
  The schema's `aligned` branch additionally requires non-null
  `apr_result_ref`, `clp_result_ref`, and `shard_summary_ref`. The
  `aligned` branch also requires `shard_artifact_refs` /
  `apr_shard_refs` / `clp_shard_refs` / `github_shard_refs` to each
  carry at least one entry; an empty ref set with three "pass"
  statuses falls through to `partial` with
  `shard_ref_set_empty_for_at_least_one_system`.
- **Test:** `test_missing_shard_summary_unknown`,
  `test_missing_apr_unknown`, `test_missing_clp_unknown`,
  `test_schema_forbids_present_aligned_without_refs`.
- **Disposition:** resolved.

### MF-06 — Builder recomputes or runs tests
- **Risk:** the parity builder secretly re-invokes the shard runner,
  re-runs pytest, or recomputes shard selection — that would make M3L
  a second eval gate and violate `docs/architecture/system_registry.md`.
- **Owner pretended:** EVL (eval execution authority).
- **Mitigation:** the builder makes no `subprocess` call, no
  `pytest.main`, no shard-runner import. Inputs are loaded as JSON
  only. The CLI never invokes any executable beyond reading the
  artifact paths the operator hands it. The unit test
  `test_builder_does_not_invoke_subprocess` patches every
  `subprocess.*` entry point to raise; the test passes because the
  builder makes no calls. `test_builder_does_not_mutate_inputs` snapshot
  checks input dicts before and after the build to confirm no in-place
  mutation.
- **Test:** `test_builder_does_not_invoke_subprocess`,
  `test_builder_does_not_mutate_inputs`.
- **Disposition:** resolved.

### MF-07 — Authority wording leak in record / reason codes
- **Risk:** an aligned parity record could leak forbidden authority
  verbs like `approve`, `certify`, `promote`, `enforce`,
  `decision`, or `verdict`, claiming gate authority that belongs to
  other systems.
- **Owner pretended:** AEX / SEL / GOV (admission and final-gate
  authority).
- **Mitigation:** the schema declares `authority_scope: const
  observation_only` and the only top-level status field is
  `parity_status`. The reason-code vocabulary is fixed and uses
  measurement nouns (`shard_artifact_missing_on_disk`,
  `apr_clp_shard_ref_mismatch`, `github_escape_apr_pass_github_non_pass`,
  `clp_github_mismatch_clp_pass_github_non_pass`,
  `shard_status_drift_observed`,
  `shard_ref_set_empty_for_at_least_one_system`,
  `shard_summary_missing`, `apr_result_missing`,
  `clp_result_missing`). The unit test
  `test_record_does_not_carry_authority_verbs_in_reason_codes` greps
  the record for the forbidden verbs and asserts none appear.
- **Test:** `test_record_does_not_carry_authority_verbs_in_reason_codes`,
  `test_record_has_no_readiness_or_gate_fields`.
- **Disposition:** resolved.

### MF-08 — Artifact refs missing but not flagged
- **Risk:** the schema's `mismatch_finding` `$def` allows
  `artifact_refs` to be empty, so a finding could claim a status drift
  without naming any backing artifact.
- **Owner pretended:** EVL (artifact-backed evidence rule).
- **Mitigation:** every detection branch in `detect_parity` populates
  `artifact_refs` with the union or intersection of the involved ref
  sets. The two cases that legitimately have empty refs are
  `shard_status_drift_observed` (a status-only drift between systems
  whose shard refs all match) and `shard_ref_set_empty_for_at_least_one_system`
  (one system reports zero refs); both name the underlying status / ref
  observation in the `message` and surface the matching reason code.
  The `aligned` branch of the schema forbids any `mismatch_findings`,
  so an "aligned" record with empty refs cannot exist.
- **Test:** `test_apr_pass_github_fail_drift_with_github_escape`
  (asserts the `github_escape` finding carries the GitHub shard refs).
- **Disposition:** resolved.

### MF-09 — Builder secretly produces readiness or gate decisions
- **Risk:** the parity record creeps into emitting a `pr_ready_status`
  or `gate_status` field, becoming a de-facto fourth gate.
- **Owner pretended:** AEX / CDE / SEL (readiness and gate authority).
- **Mitigation:** the schema's `additionalProperties: false` blocks
  any field outside the declared list. The declared list contains no
  `*_ready_*`, no `gate_status`, no `promote`, no `approve`. The unit
  test `test_record_has_no_readiness_or_gate_fields` enumerates the
  record keys and rejects any forbidden token (with `parity_status`
  explicitly allowed as the measurement vocabulary).
- **Test:** `test_record_has_no_readiness_or_gate_fields`.
- **Disposition:** resolved.

## Summary

All `must_fix` findings are resolved in this slice. M3L-03 introduces
no gate, no readiness signal, and no authority verb. The artifact is
observation-only and surfaces shard parity drift between APR, CLP, and
the GitHub-driven shard runner — that is its entire authority surface.
