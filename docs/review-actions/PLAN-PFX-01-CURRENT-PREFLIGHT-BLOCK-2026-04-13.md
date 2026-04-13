# PLAN — PFX-01 Current Contract Preflight BLOCK Repair + Governed Auto-Repair (2026-04-13)

## Prompt type
`BUILD`

## Artifact-grounded diagnosis (from generated preflight outputs)
Current BLOCK is caused by test failures surfaced in preflight report artifacts:
1. `producer_failures`: `tests/test_done_certification.py` failing because recent authority-lineage gate in `run_done_certification` now blocks legacy pass/warn/freeze paths without TAX/BAX/CAX refs.
2. `producer_failures`: `tests/test_system_handoff_integrity.py` failing because canonical handoff path was overwritten (`TPA -> FRE` removed) instead of extended.
3. `consumer_failures`: mirrored `tests/test_done_certification.py` failure.

Notably absent in artifacts:
- no schema example failures
- no missing required surface failures
- no pqx required context failures
- no trust-spine cohesion block

## In-scope files
1. `spectrum_systems/modules/governance/done_certification.py`
   - Narrow authority-lineage gating to explicit strict mode / explicit refs so existing governed flows are not silently reclassified.
2. `spectrum_systems/modules/runtime/system_registry_enforcer.py`
   - Restore existing canonical handoff edges and extend with TAX/BAX/CAX edges instead of replacing legacy edges.
3. `tests/test_done_certification.py` and/or targeted new tests (only if needed)
   - Validate compatibility and strict authority-lineage path behavior.
4. `spectrum_systems/modules/runtime/github_pr_autofix_contract_preflight.py` (new)
   - Add governed, bounded, artifact-first preflight BLOCK auto-repair runtime.
5. `scripts/run_github_pr_autofix_contract_preflight.py` (new)
   - Repo-native entrypoint.
6. Contract artifacts for auto-repair records (new schemas/examples + standards manifest updates).
7. `tests/test_github_pr_autofix_contract_preflight.py` (new)
   - Required fail-closed + bounded behavior tests.
8. Optional workflow transport update for same-repo safe context only.
9. Final review artifact: `docs/reviews/pfx_01_current_fix_and_systemwide_autorepair.md`.

## Validation and reruns
- Targeted seam tests:
  - `pytest -q tests/test_done_certification.py tests/test_system_handoff_integrity.py tests/test_contract_preflight.py`
- New auto-repair tests:
  - `pytest -q tests/test_github_pr_autofix_contract_preflight.py`
- Contract validations (required by contracts scope):
  - `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
  - `python scripts/run_contract_enforcement.py`
  - `.codex/skills/contract-boundary-audit/run.sh`
- Re-run preflight using provided command shape and confirm non-BLOCK for this local failure case.

## Scope exclusions
- No weakening of preflight BLOCK/FREEZE semantics.
- No redesign of PQX policy, TPA gate semantics, or CDE closure ownership.
- No broad refactor of existing autofix systems outside preflight-specific bounded path.
