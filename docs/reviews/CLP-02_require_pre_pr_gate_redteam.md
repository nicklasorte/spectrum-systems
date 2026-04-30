# CLP-02 Red-Team Review — Require Core Loop Pre-PR Gate Evidence

Date: 2026-04-30
Scope: CLP-02 — make `core_loop_pre_pr_gate_result` and the
`agent_pr_ready_result` guard required pre-PR evidence for repo-mutating
agent work.

CLP-02 surfaces under review:

- `docs/governance/core_loop_pre_pr_gate_policy.json`
- `contracts/schemas/core_loop_pre_pr_gate_result.schema.json`
- `contracts/examples/core_loop_pre_pr_gate_result.example.json`
- `contracts/schemas/agent_pr_ready_result.schema.json`
- `contracts/examples/agent_pr_ready_result.example.json`
- `contracts/standards-manifest.json` (agent_pr_ready_result registration)
- `scripts/run_core_loop_pre_pr_gate.py` (`--policy` + source_artifacts_used)
- `scripts/check_agent_pr_ready.py` (new guard)
- `scripts/run_pre_pr_reliability_gate.py` (`--clp-result` PRL consumer)
- `spectrum_systems/modules/runtime/core_loop_pre_pr_gate_policy.py`
- `spectrum_systems/modules/runtime/agent_core_loop_proof.py`
- `spectrum_systems/modules/prl/clp_consumer.py`
- `docs/architecture/clp_02_pr_ready_admission.md`
- `docs/architecture/system_registry.md` (CLP-02 registry section)
- `AGENTS.md`, `CLAUDE.md`, `tests/AGENTS.md` (CLP-02 rule blocks)

Each finding is categorized as **must_fix**, **should_fix**, or **observation**.

---

## 1. Agent marks PR-ready with no CLP artifact

**Vector:** Agent skips CLP entirely and asks for PR-ready handoff.

**Coverage:**

- AGL: `_load_clp_evidence` returns `None`; for repo-mutating slices,
  `compliance_status="BLOCK"` and a `clp_evidence_missing` learning action
  is emitted (`spectrum_systems/modules/runtime/agent_core_loop_proof.py`).
- PR-ready guard: `evaluate_pr_ready` with `clp_result=None` and policy
  rule `missing_clp_evidence_blocks_pr_ready=true` → `pr_ready_status=
  not_ready` with `reason_codes=["clp_evidence_missing"]`.

**Disposition:** observation — covered.

## 2. CLP result is missing but AGL still passes

**Vector:** Agent supplies a stale or unrelated artifact path.

**Coverage:**

- `_load_clp_evidence` returns `None` whenever `artifact_type !=
  "core_loop_pre_pr_gate_result"`. Existing test
  `test_agl_treats_invalid_clp_artifact_as_missing` exercises this. AGL
  routes to `compliance_status=BLOCK`.
- CLP-02 adds `_load_pr_ready_evidence` with the same fail-closed pattern
  for guard artifacts.

**Disposition:** observation — covered.

## 3. CLP gate_status=block but PR-ready guard allows

**Vector:** Guard misreads a `block` artifact as `ready`.

**Coverage:**

- `evaluate_pr_ready` short-circuits on `gate_status=="block"` to
  `not_ready` with the CLP failure_classes copied into reason_codes.
- New tests assert the guard returns exit code 2 and emits
  `pr_ready_status=not_ready` for any CLP block fixture.

**Disposition:** observation — covered.

## 4. CLP warn with unapproved reason code allows

**Vector:** Policy `allowed_warn_reason_codes` is empty (default), but a
warn slips through as ready.

**Coverage:**

- `evaluate_pr_ready` collects every check's warn reason codes and
  fail-closes when any code is outside `allowed_warn_reason_codes`. The
  rule `clp_warn_requires_explicit_allow` defaults to true and is asserted
  in `test_check_agent_pr_ready.py::test_warn_with_unapproved_reason_blocks`.

**Disposition:** observation — covered.

## 5. Missing authority-shape output counts as pass

**Vector:** Authority shape preflight produces no output file but exits 0.

**Coverage:**

- Existing CLP runner (`_check_authority_shape`) emits `status=block` with
  `failure_class=missing_required_artifact` when the output file is
  absent.
- The pure-logic `evaluate_gate` rejects any required check missing an
  `output_ref`. Existing test
  `test_missing_required_check_output_blocks` exercises the invariant.

**Disposition:** observation — covered.

## 6. Missing authority-leak output counts as pass

**Vector:** Authority leak guard exits 0 but no output file is written.

**Coverage:**

- `_check_authority_leak` emits `status=block` with
  `failure_class=missing_required_artifact` when the output file is absent.
- `evaluate_gate` blocks on missing `output_ref`.

**Disposition:** observation — covered.

## 7. Contract preflight contract_mismatch does not block

**Vector:** Contract preflight returns `BLOCK` but downstream consumers
ignore.

**Coverage:**

- CLP runner: `_check_contract_preflight` reads
  `control_signal.strategy_gate_decision` and treats `BLOCK`/`FREEZE` as
  `status=block`.
- PRL consumer: `CLP_TO_PRL_FAILURE_CLASS` maps both
  `contract_preflight_block` and `contract_mismatch` into PRL's
  `contract_schema_violation`, which carries `gate_signal=failed_gate`.

**Disposition:** observation — covered.

## 8. TLS stale artifact does not block

**Vector:** TLS regeneration produces drift but the gate ignores it.

**Coverage:**

- CLP runner runs `build_tls_dependency_priority.py` and
  `generate_ecosystem_health_report.py`, then hashes a fixed list of
  artifact paths before/after. Any digest delta forces
  `status=block` with `failure_class=tls_generated_artifact_stale`.
- Test `test_tls_freshness_drift_blocks` exercises the diff path. PRL
  consumer maps `tls_generated_artifact_stale` →
  `missing_required_artifact` (`failed_gate`).

**Disposition:** observation — covered.

## 9. Generated artifact freshness check is skipped

**Vector:** Operator passes `--skip tls_generated_artifact_freshness`.

**Coverage:**

- The runner's `--skip` flag is documented as DEBUG ONLY. Skipping a
  required check causes `evaluate_gate` to add
  `missing_required_check_output` and force `gate_status=block` for any
  repo-mutating slice. Existing test
  `test_tls_freshness_skip_blocks_repo_mutating` confirms the behavior.

**Disposition:** observation — covered.

## 10. Selected tests missing for governed surface does not block

**Vector:** Changed file lacks a canonical pytest selector mapping.

**Coverage:**

- `_check_selected_tests` uses `resolve_required_tests` plus the
  `is_docs_only_non_governed` heuristic. For governed changes with no
  selected tests, the runner emits `status=block` with
  `failure_class=pytest_selection_missing` and reason
  `no_tests_selected_for_governed_changes`. Test
  `test_selected_tests_skip_in_repo_mutating_blocks` exercises this.

**Disposition:** observation — covered.

## 11. CLP claims approval/certification/promotion/enforcement authority

**Vector:** Schema/example or runner emits authority-bearing language.

**Coverage:**

- `core_loop_pre_pr_gate_result` and `agent_pr_ready_result` schemas pin
  `authority_scope` to the const string `observation_only` and include no
  approve/certify/promote/enforce fields.
- Existing test `test_clp_does_not_claim_authority` asserts no forbidden
  vocabulary.
- Policy `must_not_do` enumerates approve / certify / promote / enforce /
  admit / execute / auto_apply_repairs / suppress_existing_gates.
- New test `test_core_loop_pre_pr_gate_policy.py::test_policy_authority_scope_is_observation_only`
  asserts the policy artifact itself never claims authority.

**Disposition:** observation — covered.

## 12. AEX/PQX direct path can bypass CLP and still appear compliant

**Vector:** Agent runs PQX directly, never invokes CLP, and ships PR-ready.

**Status:** **observation — partial coverage with documented gap.**

- AGL fail-closes on missing CLP evidence and missing/blocking PR-ready
  guard, so any AGL record produced for a repo-mutating slice without
  CLP evidence reports `compliance_status=BLOCK`.
- The CLP-02 PR-ready guard is the canonical evidence consumed downstream.
- **Documented gap:** Direct hard enforcement inside AEX admission and PQX
  closure paths is intentionally out of scope for CLP-02. The expectation
  is recorded in `docs/architecture/clp_02_pr_ready_admission.md`. Any
  future enforcement must be added by the AEX/PQX system owners; CLP must
  not redefine those entry paths.

**Disposition:** observation — documented hardening gap (not a CLP-02
authority overreach).

## 13. PRL ignores CLP block

**Vector:** PRL pre-PR reliability gate runs but never consumes the CLP
block evidence.

**Coverage:**

- `spectrum_systems/modules/prl/clp_consumer.py` provides
  `parsed_failures_from_clp_result` mapping CLP failure classes onto the
  PRL `KNOWN_FAILURE_CLASSES`.
- `scripts/run_pre_pr_reliability_gate.py` accepts `--clp-result` and
  runs the CLP-derived ParsedFailures through the standard
  classify/repair/eval pipeline. PRL retains all repair authority; CLP-02
  performs no auto-repair.
- Test `test_check_agent_pr_ready.py::test_clp_block_normalizes_to_prl_classes`
  exercises the mapping table.

**Disposition:** observation — covered.

---

## Cross-cutting checks

- Schemas have `additionalProperties: false`. ✅
- `agent_pr_ready_result` schema pins `pr_ready_status=ready` to
  `human_review_required=false`. ✅
- Policy artifact authority_scope = observation_only. ✅
- Policy `must_not_do` matches the must_not_do list in the system registry
  CLP-02 entry. ✅
- AGENTS.md / CLAUDE.md updated with CLP-02 rule block (concise). ✅
- tests/AGENTS.md references the CLP-02 test bundle. ✅

## Summary

- must_fix: **0**
- should_fix: **0**
- observation: **13** (all covered or documented)

The remaining hardening gap (item 12 — AEX/PQX direct path enforcement) is
intentional and recorded in `docs/architecture/clp_02_pr_ready_admission.md`.
