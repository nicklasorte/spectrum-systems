# APU-3LS-01 — Red-Team Review

This is an adversarial review of the APU-3LS-01 PR-update readiness
evidence gate as implemented on this branch. APU is observation-only;
canonical authority remains with AEX (admission), PQX (execution
closure), EVL (eval evidence), TPA (policy/scope), CDE
(continuation/closure), SEL (final gate signal), LIN (lineage), REP
(replay), and GOV per `docs/architecture/system_registry.md`.

Findings are categorised as `must_fix`, `should_fix`, or `observation`.

## must_fix

### MF-01 — Missing artifacts treated as present
- **Risk:** an agent could produce an `agent_pr_update_ready_result`
  that lists every leg as `present` even though no real CLP/AGL
  evidence exists.
- **Mitigation in this PR:** `evaluate_pr_update_ready` initialises
  every required leg as `missing` with a deterministic
  `<leg>_evidence_missing` reason code, then only upgrades when the
  loaded AGL record carries an artifact-backed leg. Schema requires
  `minItems: 1` on `artifact_refs` whenever `status=present`.
- **Test:** `test_repo_mutating_true_missing_clp_yields_not_ready`,
  `test_repo_mutating_true_missing_agl_yields_not_ready`,
  `test_claimed_3ls_usage_without_artifact_refs_blocks`.
- **Disposition:** resolved.

### MF-02 — `present` without `artifact_refs`
- **Risk:** prose-only "PQX present" with no real ref.
- **Mitigation:** `_normalize_leg` downgrades `present` with empty
  `artifact_refs` to `partial`, appends a
  `<leg>_present_without_artifact_refs` invalid reason code, and the
  evaluator surfaces `leg_present_without_artifact_refs`.
- **Test:** `test_present_leg_without_artifact_refs_is_downgraded`,
  `test_pr_body_prose_cannot_substitute_for_artifact_refs`.
- **Disposition:** resolved.

### MF-03 — `partial`/`missing`/`unknown` legs without `reason_codes`
- **Risk:** silent failures look like "noise" instead of evidence
  gaps.
- **Mitigation:** schema `$defs/leg_evidence` enforces
  `reason_codes minItems: 1` for non-present statuses; `_normalize_leg`
  injects a synthetic reason code and surfaces
  `<leg>_<status>_without_reason_codes`.
- **Test:** `test_partial_leg_without_reason_codes_is_invalid`.
- **Disposition:** resolved.

### MF-04 — `unknown` counted as present
- **Risk:** an agent reports `unknown` and a downstream consumer
  treats it as good enough.
- **Mitigation:** `unknown` is its own status and is never upgraded;
  `_full_evidence_yields_ready` only returns `ready` when every required
  leg is `present` (or `not_required` per policy) and never when any
  leg is `unknown`. Required-leg coverage adds a
  `<leg>_evidence_unknown` reason code that forces `not_ready`.
- **Test:** `test_unknown_leg_does_not_count_as_present`.
- **Disposition:** resolved.

### MF-05 — Missing CLP treated as PR-update ready
- **Risk:** repo-mutating slice marked ready with no CLP evidence at
  all.
- **Mitigation:** `repo_mutating_requires_clp_evidence: true` rule;
  `clp_evidence_missing` reason code; CLP slot defaults to
  `status=missing` with a reason code.
- **Test:** `test_repo_mutating_true_missing_clp_yields_not_ready`.
- **Disposition:** resolved.

### MF-06 — CLP block treated as PR-update ready
- **Risk:** `gate_status=block` from CLP ignored.
- **Mitigation:** `clp_block_status_blocks_pr_update_ready: true`
  rule emits `clp_status_block` and lifts the CLP failure classes
  into the APU reason codes.
- **Test:** `test_repo_mutating_true_clp_block_yields_not_ready`.
- **Disposition:** resolved.

### MF-07 — Unallowed CLP warn treated as clean
- **Risk:** CLP warn passes through with arbitrary reason codes.
- **Mitigation:** `clp_warn_requires_explicit_allow: true`;
  `blocked_warning_reason_codes` recorded on the artifact;
  `clp_warning_not_policy_allowed` reason code surfaced. Default
  `allowed_warning_reason_codes` is the empty list, so any warn
  blocks unless explicitly listed.
- **Test:** `test_clp_warn_unallowed_reason_blocks`,
  `test_clp_warn_partial_unallowed_still_blocks`.
- **Disposition:** resolved.

### MF-08 — Missing APU evidence still allows PR update readiness
- **Risk:** the gate self-asserts ready without producing the
  evidence artifact.
- **Mitigation:** APU emits its own evidence slot referencing the
  output artifact path, and consumers (AEX/PQX/CDE/SEL via existing
  CLP-02 wiring) can inspect the file. The schema requires a
  non-empty `evidence.APU.artifact_refs` whenever
  `evidence.APU.status=ready`.
- **Test:** `test_full_evidence_yields_ready` (APU evidence ref
  present), `test_example_artifact_validates`.
- **Disposition:** resolved.

### MF-09 — PR body prose counted as evidence
- **Risk:** the PR description is treated as artifact evidence.
- **Mitigation:** APU only consumes structured artifacts
  (`core_loop_pre_pr_gate_result`, `agent_core_loop_run_record`,
  `agent_pr_ready_result`). Prose fields in non-canonical-evidence
  paths cannot enter `artifact_refs`. A leg whose only "evidence" is
  prose (e.g. `reason_codes=["see_pr_body"]`) is treated as
  `partial`. Policy rule
  `pr_body_prose_is_not_artifact_evidence: true` documents the
  invariant.
- **Test:** `test_pr_body_prose_cannot_substitute_for_artifact_refs`.
- **Disposition:** resolved.

### MF-10 — Claimed 3LS usage without artifact refs
- **Risk:** an AGL record with `compliance_status=PASS` but no leg
  artifact refs.
- **Mitigation:** `_evidence_from_agl` lifts the per-leg shape and
  enforces the same `present requires artifact_refs` invariant; if
  AGL is missing entirely, APU emits `agl_evidence_missing`.
- **Test:** `test_claimed_3ls_usage_without_artifact_refs_blocks`,
  `test_present_leg_without_artifact_refs_is_downgraded`.
- **Disposition:** resolved.

### MF-11 — Negated authority verbs in non-owner artifacts
- **Risk:** APU schema/example/tests drift into negated authority
  language ("does not approve", "must not certify", etc.).
- **Mitigation:** schema description and policy notes use
  authority-safe wording ("emits readiness observations only",
  "canonical authority remains with <OWNER_SYSTEM>"); the example
  artifact contains no negated authority verbs; tests assert that
  the PR evidence section markdown contains no negated authority
  phrases.
- **Test:** `test_apu_artifact_negated_authority_phrases_absent_from_pr_section`,
  `test_example_does_not_claim_owner_authority`.
- **Disposition:** resolved.

## should_fix

### SF-01 — `repo_mutating` unknown
- **Risk:** caller forgets to pass `--repo-mutating`; APU silently
  defaults to ready.
- **Mitigation:** `repo_mutating_unknown_yields_not_ready: true`
  rule emits `repo_mutating_unknown`; the script's `--repo-mutating`
  argument supports an explicit `unknown` mode for testing the
  fail-closed path.
- **Test:** `test_repo_mutating_unknown_yields_not_ready`.
- **Disposition:** resolved.

### SF-02 — Missing required CLP check observation
- **Risk:** CLP gate passes on a partial check set (e.g.
  `contract_preflight` missing).
- **Mitigation:** `missing_required_check_observation_blocks: true`
  rule with `required_clp_check_observations` from policy; emits a
  per-check `missing_check_<name>` reason code. CLP-01 already
  blocks on a missing required check; APU doubles the invariant so
  the readiness artifact records it explicitly.
- **Test:** `test_missing_required_check_observation_blocks`.
- **Disposition:** resolved.

### SF-03 — `agent_pr_ready_result` not_ready
- **Risk:** a downstream consumer ignores the upstream CLP-02 guard.
- **Mitigation:** APU passes through `pr_ready_status` from the
  guard; `not_ready` becomes `agent_pr_ready_status_not_ready` and
  forces `not_ready`.
- **Test:** `test_agent_pr_ready_not_ready_yields_not_ready`.
- **Disposition:** resolved.

### SF-04 — `agent_pr_ready_result` `human_review_required`
- **Risk:** silently downgraded to `not_ready`.
- **Mitigation:** `human_review_required` propagates and APU emits
  `readiness_status=human_review_required`.
- **Test:** `test_agent_pr_ready_human_review_required_propagates`.
- **Disposition:** resolved.

### SF-05 — CLP authority-scope drift
- **Risk:** CLP artifact with `authority_scope != observation_only`.
- **Mitigation:** `authority_scope_drift` reason code +
  `human_review_required=true`.
- **Test:** `test_clp_authority_scope_drift_yields_human_review`.
- **Disposition:** resolved.

### SF-06 — Stale generated TLS artifacts pass
- **Risk:** APU is read but generated TLS artifacts drifted.
- **Mitigation:** APU consumes CLP, which already runs the TLS
  freshness check; APU's policy lists
  `tls_generated_artifact_freshness` as a required CLP check
  observation, so a missing TLS check forces APU `not_ready`.
- **Test:** `test_missing_required_check_observation_blocks`.
- **Disposition:** resolved.

### SF-07 — Repair attempt count exceeds 2
- **Risk:** APU implies PRL auto-repair.
- **Mitigation:** `max_repair_attempts: 0` in the APU policy; APU
  emits no auto-repair action and only adds `required_follow_up`
  hints owned by PRL/TPA/AGL.
- **Test:** Implicitly validated by reading the policy file; APU
  emits no repair actions in any of the test paths.
- **Disposition:** resolved.

## observation

### OB-01 — APU is observation-only
- APU emits PR-update readiness observations only. Canonical
  authority remains with AEX/PQX/EVL/TPA/CDE/SEL/LIN/REP/GOV.
  APU's schema pins `authority_scope: observation_only` via a
  `const` constraint.

### OB-02 — `evidence_hash` is informational
- The hash is a structural digest of the evidence shape, used for
  replay/lineage. It is not a tamper-resistant signature; do not
  treat it as one.

### OB-03 — MET claims authority
- MET is observation-only; APU does not delegate any control or
  final-gate signal authority to MET. APU consumes only
  CLP/AGL/CLP-02-guard inputs.

### OB-04 — PRL auto-repair implied by APU
- APU does not auto-repair. `max_repair_attempts: 0`. APU emits
  follow-up hints owned by PRL/TPA/AGL; the actual repair surface
  remains with PRL/FRE/CDE/PQX per the system registry.

### OB-05 — schema drift surface
- Future schema revisions to `agent_core_loop_run_record` (e.g. new
  legs) need a corresponding update to APU's required-leg list and
  `_evidence_from_agl` mapping.
