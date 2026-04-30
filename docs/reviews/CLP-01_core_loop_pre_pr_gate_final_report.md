# CLP-01 Core Loop Pre-PR Gate — Final Report

## Failures this catches earlier (relative to AGL-01 CI-time failures)

The CLP-01 pre-PR gate runs the canonical pre-admission check bundle before
a repo-mutating Codex/Claude slice can be handed off as PR-ready. Each of
the following failures, all observed in successive AGL-01 PR rounds, would
now be caught by the pre-PR gate and forced to `gate_status=block` (exit 2)
*before* PR creation/update:

1. **authority_shape_violation** — `_check_authority_shape` reads
   `outputs/core_loop_pre_pr_gate/authority_shape_preflight_result.json`
   and maps any non-zero rc or `payload.status=fail` to a CLP block
   (`failure_class=authority_shape_violation`).
2. **authority_leak_guard_failure** — `_check_authority_leak` maps
   non-zero rc / `payload.status=fail` to a CLP block
   (`failure_class=authority_leak_violation`).
3. **contract_preflight schema_violation** — `_check_contract_preflight`
   reads `control_signal.strategy_gate_decision` and maps `BLOCK`/`FREEZE`
   to a CLP block (`failure_class=contract_preflight_block`).
4. **stale TLS generated artifact** — `_check_tls_freshness` hashes the
   canonical TLS / ecosystem-health artifact set before and after running
   `build_tls_dependency_priority` and `generate_ecosystem_health_report`;
   any post-run drift is mapped to a CLP block
   (`failure_class=tls_generated_artifact_stale`).
5. **stale TLS again after test changes** — same logic; the freshness
   detection is hash-based and re-evaluated per run, so a forgotten
   regenerate after any file change blocks before PR-ready.

Additionally, the gate blocks any of the following independent of AGL-01:

- contract enforcement findings (`contract_enforcement_violation`)
- selected-test failure (`selected_test_failure`)
- empty test selection on governed changes (`pytest_selection_missing`)
- a missing or non-executable required check (`missing_required_check_output`)
- an unknown failure class (forces `gate_status=block` AND
  `human_review_required=true`)

## Files changed / added

Added:

- `contracts/schemas/core_loop_pre_pr_gate_result.schema.json`
- `contracts/examples/core_loop_pre_pr_gate_result.example.json`
- `spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py`
- `scripts/run_core_loop_pre_pr_gate.py`
- `tests/test_core_loop_pre_pr_gate.py`
- `docs/reviews/CLP-01_core_loop_pre_pr_gate_redteam.md`
- `docs/reviews/CLP-01_core_loop_pre_pr_gate_final_report.md`
- `docs/review-actions/CLP-01_fix_actions.md`

Modified:

- `contracts/standards-manifest.json` — registered
  `core_loop_pre_pr_gate_result` (artifact_class `coordination`,
  introduced_in `CLP-01`).
- `spectrum_systems/modules/runtime/agent_core_loop_proof.py` — added
  optional `clp_evidence_artifact` parameter; missing/blocked CLP
  evidence on a repo-mutating slice forces
  `compliance_status=BLOCK` and emits a `clp_evidence_missing` /
  `resolve_clp_block` learning action with `owner_system=PRL`.
- `docs/architecture/system_registry.md` — added CLP-01 entry under
  "Recurring Cross-System Phase Labels (Non-Owner)" with explicit
  `must_not_do` for every authority verb; updated PRL `Upstream
  Dependencies` to cite CLP evidence.
- `docs/governance/preflight_required_surface_test_overrides.json` —
  bound the new schema/example/script/runtime files to
  `tests/test_core_loop_pre_pr_gate.py` and `tests/test_contracts.py`.
- `contracts/governance/authority_shape_vocabulary.json` — added the new
  CLP files to `guard_path_prefixes` (consistent with the existing
  treatment of governed gate scripts).
- `contracts/governance/authority_registry.json` — added per-path
  `allowed_values` overrides for the new CLP files (consistent with the
  existing pattern for `scripts/run_pr_gate.py`,
  `spectrum_systems/modules/runtime/pr_test_selection.py`, etc.).

## 3LS owner mapping

| Check                                | Owner system | 3LS overlay | Rationale |
|--------------------------------------|--------------|-------------|-----------|
| `authority_shape_preflight`          | AEX          | TPA         | Admission boundary terminology / policy adjudication |
| `authority_leak_guard`               | AEX          | TPA         | Admission boundary terminology / policy adjudication |
| `contract_enforcement`               | EVL          | —           | Schema / contract eval evidence |
| `tls_generated_artifact_freshness`   | LIN          | OBS, REP    | Lineage of generated artifacts; observability + replayability of trust spine evidence |
| `contract_preflight`                 | EVL          | TPA         | Contract / preflight eval evidence; policy adjudication |
| `selected_tests`                     | EVL          | —           | Test eval evidence (canonical pytest selection via `pr_test_selection`) |

CLP-01 itself owns no authority. It is a bundle runner / evidence artifact
under the "Recurring Cross-System Phase Labels (Non-Owner)" section of the
system registry. Final authorities remain with AEX, PQX, EVL, TPA, CDE,
and SEL. PRL/RIL/FRE may diagnose and propose repairs based on the CLP
evidence; CDE owns the final continue/repair/block decision.

## Red-team findings and fixes

11 must_fix findings were identified and fixed in this same change set.
See `docs/reviews/CLP-01_core_loop_pre_pr_gate_redteam.md` and
`docs/review-actions/CLP-01_fix_actions.md`. Summary:

- MF-01..02 — bundle cannot omit authority-shape or authority-leak checks.
- MF-03 — stale TLS artifact detected via before/after hash diff.
- MF-04 — contract preflight `BLOCK`/`FREEZE` propagates to CLP block.
- MF-05 — schema rejects pass/warn/block status without `output_ref`.
- MF-06 — unknown failure class forces block + `human_review_required=true`.
- MF-07 — `authority_scope` pinned to `observation_only`; registry entry
  enumerates `must_not_do` for every authority verb.
- MF-08..09 — skipping a required check on repo-mutating work blocks via
  `missing_required_check_output`.
- MF-10 — gate cannot pass when any required check blocks; schema enforces
  `first_failed_check=null` and `human_review_required=false` when
  `gate_status=pass`.
- MF-11 — AGL `agent_core_loop_run_record` reports missing CLP evidence
  for repo-mutating work and forces `compliance_status=BLOCK`.

No unresolved must_fix findings remain.

## Tests run

```
python -m pytest tests/test_core_loop_pre_pr_gate.py -q
  -> 31 passed
python -m pytest tests/test_agent_core_loop_proof.py -q
  -> 11 passed
python -m pytest tests/test_contracts.py -q
  -> 98 passed
python -m pytest tests/ -k "agent_core_loop or core_loop_pre_pr or contracts" -q
  -> 206 passed
python scripts/run_contract_enforcement.py
  -> failures=0 warnings=0 not_yet_enforceable=0  (exit 0)
python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json
  -> status=pass, violation_count=0  (exit 0)
python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json
  -> status=pass, violation_count=0  (exit 0)
```

## AGL-01 failure-class fixture coverage

The CLP-01 test suite includes targeted tests that drive each AGL-01
failure class through the helper:

- `test_authority_shape_failure_blocks` →
  `failure_class=authority_shape_violation`,
  reason_code=`authority_shape_review_language_lint`.
- `test_authority_leak_failure_blocks` →
  `failure_class=authority_leak_violation`,
  reason_code=`forbidden_authority_value`.
- `test_stale_tls_artifact_blocks` →
  `failure_class=tls_generated_artifact_stale`,
  reason_code=`tls_generated_artifact_drift`.
- `test_tls_freshness_drift_blocks` (tmp_path) — exercises the
  `hash_paths` / `diff_hash_maps` drift detection end-to-end.
- `test_contract_preflight_block_propagates` →
  `failure_class=contract_preflight_block`.
- `test_contract_enforcement_failure_blocks` →
  `failure_class=contract_enforcement_violation`.

Each test asserts `gate_status=block`, `first_failed_check=<expected>`,
and that the artifact still validates against
`core_loop_pre_pr_gate_result`.

## Remaining gaps

- `--max-repair-attempts` is wired into the CLI but currently unused.
  Repair authority belongs to PRL/FRE/CDE/PQX; CLP-01 deliberately does
  not auto-fix. A future change can expose a "report only" mode that
  hands off to PRL's repair candidates.
- The runner does not yet emit `trace_refs` / `replay_refs` for the
  outer gate run. PRL provenance (workflow_run_id / source_commit_sha)
  is tracked separately and can be fed in via a future CLI flag.
- `_check_selected_tests` reads the entire `tests/` inventory each run
  through the canonical selector. This is acceptable today but could be
  cached.

## Next recommended step

Wire `scripts/run_core_loop_pre_pr_gate.py` into the existing PRL
pre-PR reliability gate (`scripts/run_pre_pr_reliability_gate.py`) so
that PRL consumes the CLP evidence as a structured input. This keeps
authority boundaries clean — CLP emits evidence; PRL classifies and
proposes repairs; CDE decides; AEX/PQX/EVL/TPA/SEL retain final
authority.
