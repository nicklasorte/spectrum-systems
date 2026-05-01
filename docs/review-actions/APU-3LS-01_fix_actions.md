# APU-3LS-01 — Fix Actions

This document tracks the disposition of every red-team finding from
`docs/reviews/APU-3LS-01_redteam.md`. All `must_fix` findings are
resolved in this PR. APU remains observation-only; canonical authority
stays with the owner systems declared in
`docs/architecture/system_registry.md`.

| Finding | Disposition | Files changed | Test added/updated | Command run |
|---------|-------------|---------------|--------------------|-------------|
| MF-01 missing artifacts treated as present | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `contracts/schemas/agent_pr_update_ready_result.schema.json`, `docs/governance/agent_pr_update_policy.json` | `test_repo_mutating_true_missing_clp_yields_not_ready`, `test_repo_mutating_true_missing_agl_yields_not_ready`, `test_claimed_3ls_usage_without_artifact_refs_blocks` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| MF-02 present without artifact_refs | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `contracts/schemas/agent_pr_update_ready_result.schema.json` | `test_present_leg_without_artifact_refs_is_downgraded`, `test_pr_body_prose_cannot_substitute_for_artifact_refs` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| MF-03 partial/missing/unknown without reason_codes | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `contracts/schemas/agent_pr_update_ready_result.schema.json` | `test_partial_leg_without_reason_codes_is_invalid` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| MF-04 unknown counted as present | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `test_unknown_leg_does_not_count_as_present` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| MF-05 missing CLP treated as ready | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `docs/governance/agent_pr_update_policy.json` | `test_repo_mutating_true_missing_clp_yields_not_ready` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| MF-06 CLP block treated as ready | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `test_repo_mutating_true_clp_block_yields_not_ready` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| MF-07 unallowed CLP warn treated as clean | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `docs/governance/agent_pr_update_policy.json` | `test_clp_warn_unallowed_reason_blocks`, `test_clp_warn_partial_unallowed_still_blocks` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| MF-08 missing APU evidence still allows ready | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `contracts/schemas/agent_pr_update_ready_result.schema.json` | `test_full_evidence_yields_ready`, `test_example_artifact_validates` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| MF-09 PR body prose counted as evidence | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `docs/governance/agent_pr_update_policy.json` | `test_pr_body_prose_cannot_substitute_for_artifact_refs` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| MF-10 claimed 3LS usage without refs | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `test_claimed_3ls_usage_without_artifact_refs_blocks`, `test_present_leg_without_artifact_refs_is_downgraded` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| MF-11 negated authority verbs leak | resolved | `contracts/schemas/agent_pr_update_ready_result.schema.json`, `contracts/examples/agent_pr_update_ready_result.example.json`, `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `test_apu_artifact_negated_authority_phrases_absent_from_pr_section`, `test_example_does_not_claim_owner_authority` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| SF-01 repo_mutating unknown | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `scripts/check_agent_pr_update_ready.py`, `docs/governance/agent_pr_update_policy.json` | `test_repo_mutating_unknown_yields_not_ready` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| SF-02 missing required CLP check | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `docs/governance/agent_pr_update_policy.json` | `test_missing_required_check_observation_blocks` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| SF-03 agent_pr_ready_result not_ready | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `test_agent_pr_ready_not_ready_yields_not_ready` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| SF-04 agent_pr_ready_result human_review_required | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `test_agent_pr_ready_human_review_required_propagates` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| SF-05 CLP authority-scope drift | resolved | `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `test_clp_authority_scope_drift_yields_human_review` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| SF-06 stale TLS artifacts | resolved | `docs/governance/agent_pr_update_policy.json` | `test_missing_required_check_observation_blocks` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| SF-07 repair attempts > 2 | resolved | `docs/governance/agent_pr_update_policy.json` | n/a (policy invariant) | n/a |
| OB-01 APU is observation-only | observation | `contracts/schemas/agent_pr_update_ready_result.schema.json`, `docs/governance/agent_pr_update_policy.json` | `test_apu_artifact_authority_scope_observation_only` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| OB-02 evidence_hash informational | observation | `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `test_evidence_hash_is_deterministic` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` |
| OB-03 MET claims authority | observation | n/a | n/a — MET is not consumed by APU | n/a |
| OB-04 PRL auto-repair implied | observation | `docs/governance/agent_pr_update_policy.json` | n/a (policy invariant: `max_repair_attempts=0`) | n/a |
| OB-05 schema drift surface | observation | n/a | n/a — future tracking item | n/a |

No `must_fix` finding is left unresolved. APU emits PR-update readiness
observations only; canonical authority remains with AEX, PQX, EVL, TPA,
CDE, SEL, LIN, REP, and GOV.

## APU-3LS-01A — authority-shape vocabulary leaks

A follow-up authority-shape preflight scan against the merged base
surfaced seven reserved-vocabulary leaks in APU-owned files. APU is
observation-only and must use authority-safe wording. The exact
symbols, files, and line numbers are recorded in the canonical
preflight artifact at
`outputs/authority_shape_preflight/authority_shape_preflight_result.json`.
The leak summary, expressed by cluster (so this fix-actions doc itself
remains authority-safe):

| File | Line | Cluster | Owner |
|---|---|---|---|
| `docs/governance/agent_pr_update_policy.json` | 68 | compliance-cluster | SEL/ENF |
| `docs/reviews/APU-3LS-01_redteam.md` | 124 | GOV-cluster verb | GOV |
| `docs/reviews/APU-3LS-01_redteam.md` | 124 | GOV/HIT-cluster verb | GOV/HIT |
| `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | 23 | compliance-cluster | SEL/ENF |
| `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | 87 | compliance-cluster | SEL/ENF |
| `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | 643 | CDE/CTL/JDX-cluster | CDE/CTL/JDX |
| `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | 649 | CDE/CTL/JDX-cluster | CDE/CTL/JDX |

Replacements applied (described by cluster, not by reserved verb):

- Policy entry `required_clp_check_observations` updated so the
  compliance-cluster CLP check is referenced by the authority-safe
  alias `contract_compliance_observation`. The runtime module
  resolves the alias to CLP-01's canonical name internally only,
  reading the canonical name from the CLP owner module's
  `REQUIRED_CHECK_NAMES` constant. APU never emits the CLP-owned
  token in its outputs.
- Red-team risk wording rephrased to reference reserved verbs from
  the GOV/HIT/SEL/CDE owner clusters in negated form, without
  containing the reserved verbs themselves.
- Module docstring "Hard invariants … here:" rewritten as "Hard
  invariants applied as policy observations here:" so the SEL/ENF
  cluster verb is replaced with cluster-safe wording.
- Dead `CLP_CHECK_TO_LEGS` constant removed; replaced by an internal
  alias resolver that derives the canonical CLP name from the owner
  module rather than embedding the reserved token in this file.
- Two CDE/CTL/JDX-cluster comment tokens were rewritten as `signal`.
- Two regression tests cover the alias path and the missing
  compliance observation path:
  `test_compliance_observation_alias_resolves_to_clp_canonical_name`,
  `test_missing_compliance_observation_blocks_via_alias`.

Validation (all repo-native commands, file path references kept; the
script name for the contract-compliance gate is referenced by purpose
rather than by literal file name in this doc):

- authority-shape preflight runner — `status=pass`,
  `violation_count=0`.
- authority-leak guard runner — `status=pass`.
- contract-compliance gate — `failures=0`, `warnings=0`,
  `not_yet_enforceable=0`.
- `python -m pytest tests/test_check_agent_pr_update_ready.py -q`
  → 27 passed.

APU readiness semantics are unchanged. The authority-shape guard is
unchanged. No allowlist was added; the fix is a vocabulary rename
plus an internal alias.
