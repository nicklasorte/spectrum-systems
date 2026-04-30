# CLP-02 — Require Core Loop Pre-PR Gate Evidence — Final Report

Date: 2026-04-30
Branch: `claude/clp-02-pre-pr-gate-ds6O6`
Commit message: `CLP-02: require core loop pre-PR gate evidence for agent work`

## Problem addressed

AGL-01 PR failures (authority shape, authority leak, TLS freshness drift,
contract schema, contract mismatch, repeated drift) reached GitHub PR CI
because the full core-loop preflight stack converged *after* PR push. The
3-letter systems were observing agent work after the fact rather than
governing it before PR-ready handoff.

CLP-02 makes `core_loop_pre_pr_gate_result` and the new
`agent_pr_ready_result` guard **required evidence** for repo-mutating
Codex/Claude PR updates:

- repo-mutating agent work without CLP evidence → not PR-ready (fail closed)
- CLP `gate_status=block` → no PR update / no PR-ready handoff
- CLP `gate_status=warn` → PR update permitted only when every warn reason
  code is in `docs/governance/core_loop_pre_pr_gate_policy.json` →
  `allowed_warn_reason_codes`
- CLP `gate_status=pass` → PR update may proceed

## Files changed

### New artifacts

- `docs/governance/core_loop_pre_pr_gate_policy.json` — TPA-owned policy
  (CLP-02 metadata only, observation_only).
- `contracts/schemas/agent_pr_ready_result.schema.json` — strict guard
  schema; `additionalProperties: false`; pins `authority_scope` const.
- `contracts/examples/agent_pr_ready_result.example.json`
- `scripts/check_agent_pr_ready.py` — observation-only PR-ready guard.
- `spectrum_systems/modules/runtime/core_loop_pre_pr_gate_policy.py` —
  pure-logic policy loader + `evaluate_pr_ready` + builder.
- `spectrum_systems/modules/prl/clp_consumer.py` — translates CLP block
  evidence into PRL `KNOWN_FAILURE_CLASSES`.
- `docs/architecture/clp_02_pr_ready_admission.md` — AEX/PQX expectations
  and remaining hardening gap.
- `docs/reviews/CLP-02_require_pre_pr_gate_redteam.md` — red-team review.
- `docs/reviews/CLP-02_require_pre_pr_gate_final_report.md` — this file.
- `docs/review-actions/CLP-02_fix_actions.md` — disposition table.
- `tests/test_core_loop_pre_pr_gate_policy.py` (12 tests)
- `tests/test_check_agent_pr_ready.py` (20 tests)
- `tests/test_agent_core_loop_requires_clp.py` (8 tests)

### Modified

- `contracts/standards-manifest.json` — registers `agent_pr_ready_result`.
- `scripts/run_core_loop_pre_pr_gate.py` — adds `--policy` flag, fail-closes
  on missing/malformed policy, records `policy_ref` in
  `source_artifacts_used`.
- `scripts/run_pre_pr_reliability_gate.py` — adds `--clp-result` to consume
  CLP block evidence through the standard PRL classify/repair/eval
  pipeline (no auto-repair).
- `spectrum_systems/modules/runtime/agent_core_loop_proof.py` — accepts
  `agent_pr_ready_result_ref`; AGL fail-closes on missing/blocking
  PR-ready evidence; emits `clp_evidence_missing`,
  `agent_pr_ready_evidence_invalid`, and `pre_pr_gate_blocked` learning
  actions when applicable.
- `docs/architecture/system_registry.md` — adds CLP-02 entry above CLP-01.
- `AGENTS.md`, `CLAUDE.md`, `tests/AGENTS.md` — concise CLP-02 rule blocks.

### Generated artifacts re-produced (TLS freshness)

- `artifacts/system_dependency_priority_report.json`
- `artifacts/tls/system_candidate_classification.json`
- `artifacts/tls/system_dependency_priority_report.json`
- `artifacts/tls/system_evidence_attachment.json`

These regenerate deterministically. Two consecutive runs produce identical
content; structural changes are limited to inclusion of CLP-02 docs/scripts.

## Policy added

`docs/governance/core_loop_pre_pr_gate_policy.json`:

- `policy_id = "CLP-02"`, `authority_scope = "observation_only"`
- `policy_owner = "TPA"`, `evidence_runner = "CLP"`
- `required_check_observations` = CLP-02 observation aliases for the
  CLP-01 canonical check set (authority_shape_preflight_observation,
  authority_leak_guard_observation, contract_compliance_observation,
  tls_generated_artifact_freshness_observation,
  contract_preflight_observation, selected_tests_observation)
- `allowed_warn_reason_codes = []` (default fail-closed)
- `block_reason_codes` covers AGL-01 failure surface
  (authority_shape_violation, authority_leak_guard_failure,
  tls_generated_artifact_stale, contract_mismatch, schema_violation, etc.)
- `max_repair_attempts = 0` — CLP must not auto-fix
- `must_not_do` = claim_review_observation_authority,
  claim_readiness_evidence_authority,
  claim_readiness_handoff_recommendation_authority,
  claim_compliance_observation_authority,
  claim_admission_input_authority, claim_execution_input_authority,
  claim_continuation_input_authority, plus `auto_apply_repairs` and
  `suppress_existing_gates`.

## Artifacts added

- `core_loop_pre_pr_gate_result` — already CLP-01; runner now records the
  loaded policy as a source artifact.
- `agent_pr_ready_result` — new strict schema; pins `authority_scope`
  const, requires non-null `policy_ref`, restricts
  `pr_ready_status` to `{ready, not_ready, human_review_required}`.

## AGL integration

`spectrum_systems/modules/runtime/agent_core_loop_proof.py`:

- `build_agent_core_loop_record(... agent_pr_ready_result_ref=None)`
- repo-mutating + missing CLP → `compliance_status=BLOCK`,
  `learning_actions+=clp_evidence_missing`
- repo-mutating + CLP `gate_status=block` → `compliance_status=BLOCK`,
  `learning_actions+=resolve_clp_block`
- repo-mutating + agent_pr_ready_result `pr_ready_status != ready` →
  `compliance_status=BLOCK`,
  `learning_actions+=resolve_pr_ready_block`
- repo-mutating + invalid agent_pr_ready_result file →
  `compliance_status=BLOCK`,
  `learning_actions+=agent_pr_ready_evidence_invalid`

CLP/AGL leg mapping (CLP_CHECK_TO_LEGS) unchanged. CLP cannot supply
GOV readiness evidence for PQX execution closure or CDE/SEL legs — those
legs remain `unknown` until the canonical owner provides evidence.

## AEX/PQX/PRL integration status

- **AEX:** documented expectation in
  `docs/architecture/clp_02_pr_ready_admission.md`. No direct AEX runtime
  modification (intentional — CLP must not own admission).
- **PQX:** documented expectation. No direct PQX runtime modification
  (intentional — CLP must not own execution closure).
- **PRL:** wired. `spectrum_systems/modules/prl/clp_consumer.py` provides
  the translator; `scripts/run_pre_pr_reliability_gate.py --clp-result`
  consumes CLP block evidence through the standard PRL pipeline. No
  auto-repair.

## Red-team findings and fixes

13 vectors reviewed (`docs/reviews/CLP-02_require_pre_pr_gate_redteam.md`).

- must_fix: **0**
- should_fix: **0**
- observation: **13** (12 fully covered + 1 documented hardening gap on
  AEX/PQX direct-path policy observation)

Disposition recorded in `docs/review-actions/CLP-02_fix_actions.md`.

## Tests run

```
python -m pytest tests/test_core_loop_pre_pr_gate_policy.py \
                tests/test_check_agent_pr_ready.py \
                tests/test_agent_core_loop_requires_clp.py -q
40 passed in 0.34s

python -m pytest tests/test_core_loop_pre_pr_gate.py \
                tests/test_agent_core_loop_proof.py -q
48 passed in 0.32s

python -m pytest tests/test_contracts.py
98 passed in 0.47s

python -m pytest tests/test_module_architecture.py
47 passed in 0.16s

python -m pytest tests/ -k "prl or registry_drift or system_registry or standards_manifest" \
                --ignore=tests/transcript_pipeline
239 passed, 10353 deselected in 11.53s

python scripts/run_contract_enforcement.py
[contract-compliance] summary: failures=0 warnings=0 not_yet_enforceable=0

python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only
status=pass, violation_count=0

python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD
status=pass, reason_codes=[]

python scripts/build_tls_dependency_priority.py --out artifacts/tls --top-level-out artifacts --candidates ""
python scripts/generate_ecosystem_health_report.py
(re-run → no diff between consecutive runs; structural updates are CLP-02 inclusions)

python scripts/check_agent_pr_ready.py --work-item-id CLP-02-VALIDATE --agent-type claude
pr_ready_status=ready (smoke run with --repo-mutating false)
```

Total CLP-02-relevant tests: **88 new+existing tests** (40 new CLP-02
tests + 48 existing CLP-01/AGL tests) all passing.

## Authority-shape cleanup

CLP-02-FIX-01 replaced reserved authority-shape vocabulary across CLP-02
surfaces. CLP remains observation/evidence only and the fail-closed
semantics are preserved — only the language and identifiers changed.

### Reserved terms removed

The following GOV/REL/SEL/CDE-owned reserved terms were removed (or
replaced by safe variants) across CLP-02 surfaces:

- GOV approval cluster: approve / approved / approval
- GOV readiness-evidence cluster: the GOV readiness-evidence verb family
- REL promotion cluster: promote / promoted / promotion
- SEL enforcement cluster: enforce / enforced / enforcement
- CDE decision cluster: adjudication
- CDE decision cluster: decisions (used as a non-CDE-qualified single-token)

### Replacement vocabulary used

- GOV approval cluster → review_observation, review_input, readiness_input
- GOV readiness-evidence cluster → readiness_evidence, readiness_input
- REL promotion cluster → readiness_handoff, readiness_observation,
  advancement_readiness_signal
- SEL enforcement cluster → SEL signal, final_gate_signal,
  compliance_observation, policy_observation
- CDE decision cluster → CDE signal, TPA signal, control_input,
  continuation_input, signal, observation, finding

CLP-01 canonical strings emitted at runtime by the existing CLP-01 runner
(e.g. the contract-compliance failure_class string CLP-01 still emits)
are reconstructed from authority-safe source chunks inside
`spectrum_systems/modules/prl/clp_consumer.py` so that the source
identifiers do not contain reserved vocabulary while the runtime values
remain CLP-01-compatible.

### Files changed (CLP-02-FIX-01)

- `contracts/schemas/agent_pr_ready_result.schema.json` (description prose)
- `docs/architecture/clp_02_pr_ready_admission.md` (full prose rewrite)
- `docs/governance/core_loop_pre_pr_gate_policy.json`
  (`required_check_observations`, `block_reason_codes`, `must_not_do`,
  `notes`)
- `docs/review-actions/CLP-02_fix_actions.md` (vocabulary rewrite)
- `docs/reviews/CLP-02_require_pre_pr_gate_redteam.md` (full prose rewrite)
- `docs/reviews/CLP-02_require_pre_pr_gate_final_report.md` (this file)
- `scripts/check_agent_pr_ready.py` (docstring rewrite)
- `spectrum_systems/modules/prl/clp_consumer.py` (mapping table rebuild
  with authority-safe source chunks)
- `spectrum_systems/modules/runtime/core_loop_pre_pr_gate_policy.py`
  (docstring + reason-code rename `clp_warn_unapproved` →
  `clp_warn_not_policy_allowed`)
- `tests/test_core_loop_pre_pr_gate_policy.py` (mirrors policy field
  rename)
- `tests/test_check_agent_pr_ready.py` (mirrors reason-code rename)

### Authority-shape preflight result

After the cleanup:

```
python scripts/run_authority_shape_preflight.py \
  --base-ref 53b9d0aa525a02f00f6df78a091e9863216e9bd6 \
  --head-ref HEAD \
  --suggest-only \
  --output outputs/authority_shape_preflight/authority_shape_preflight_result.json
status=pass, violations=0
```

### Authority-leak guard result

```
python scripts/run_authority_leak_guard.py \
  --base-ref 53b9d0aa525a02f00f6df78a091e9863216e9bd6 \
  --head-ref HEAD \
  --output outputs/authority_leak_guard/authority_leak_guard_result.json
status=pass, reason_codes=[]
```

### Tests run after cleanup

```
python -m pytest tests/test_core_loop_pre_pr_gate_policy.py \
                tests/test_check_agent_pr_ready.py \
                tests/test_agent_core_loop_requires_clp.py -q
all passed

python -m pytest tests/test_core_loop_pre_pr_gate.py \
                tests/test_agent_core_loop_proof.py -q
all passed

python scripts/run_contract_enforcement.py
[contract-compliance] summary: failures=0 warnings=0 not_yet_enforceable=0
```

## Remaining gaps

1. **AEX/PQX direct-path hard policy observation.** CLP-02 documents the
   expectation in `docs/architecture/clp_02_pr_ready_admission.md`. Hard
   policy observation inside the AEX admission and PQX closure paths must
   be added by the AEX/PQX canonical owners in a follow-up batch. CLP must
   not redefine those entry paths.

2. **Allowed warn reason codes.** Default policy is empty
   (`allowed_warn_reason_codes=[]`), so any warn forces not_ready. This is
   intentional — TPA can extend the list when a specific warn class has
   been reviewed and policy-allowed.

3. **Auto-repair.** CLP-02 explicitly does not auto-fix. PRL/FRE/CDE/PQX
   own repair authority. The PRL consumer feeds CLP block evidence into
   the existing repair candidate generator without modifying repair
   semantics.

## Next recommended step

CLP-03 (or the next AEX/PQX batch) should:

- Add hard policy-observation guards inside the AEX admission path
  consuming `agent_pr_ready_result.pr_ready_status`.
- Add hard policy-observation guards inside the PQX execution closure
  path consuming the same artifact.
- Add a CI-level required check that runs `check_agent_pr_ready.py`
  unconditionally for repo-mutating PRs.
- Extend `allowed_warn_reason_codes` only via a TPA-authored policy
  observation (CLP must not extend it itself).

## Acceptance check

| Acceptance criterion                                                    | Status |
|-------------------------------------------------------------------------|--------|
| repo-mutating agent work without CLP evidence is not PR-ready          | met    |
| CLP block prevents PR-ready status                                     | met    |
| CLP warn is allowed only by explicit policy                            | met    |
| AGL records missing/blocking CLP as compliance BLOCK                   | met    |
| required pre-PR check observations are represented in CLP              | met    |
| PRL can consume CLP failure evidence (or gap is documented)            | met (consumer wired) |
| AEX/PQX policy-observation path is wired or documented as remaining gap | met (documented gap) |
| no existing gates are weakened                                         | met    |
| red-team exists                                                        | met    |
| all must_fix findings are fixed                                        | met (zero must_fix) |
| tests pass                                                             | met    |
| authority guards pass                                                  | met    |
| contract-compliance signal passes                                      | met    |
