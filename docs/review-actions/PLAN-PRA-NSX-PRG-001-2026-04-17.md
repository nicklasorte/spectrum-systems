# PLAN-PRA-NSX-PRG-001-2026-04-17

Primary Prompt Type: BUILD

## Repo inspection summary
- Reviewed canonical owner map in `docs/architecture/system_registry.md` and confirmed PRA/NSX are not yet canonically defined.
- Reviewed PR #1105 follow-through surfaces: `scripts/run_shift_left_preflight.py`, `scripts/run_shift_left_entrypoint_coverage_audit.py`, and related SLH tests.
- Reviewed contract authority surfaces under `contracts/schemas/`, `contracts/examples/`, and `contracts/standards-manifest.json`.
- Reviewed existing runtime github ingestion/autofix patterns in `spectrum_systems/modules/runtime/` for repo-native deterministic PR metadata handling.

## Current state inherited from PR #1105
- SLH preflight wrapper is implemented and blocks fail-open execution paths.
- Deterministic remediation hints and targeted rerun declarations are present at script entrypoints.
- Entrypoint coverage audit exists for key scripts.
- Workflow-level SLH enforcement, PRA/NSX/PRG automation chain, and weak-seam producer audits are not yet complete.

## Exact files to add/modify
- Add runtime module implementing PRA→NSX→PRG loop and weak-seam/workflow audit helpers.
- Add/modify scripts for orchestration and workflow-level SLH auditing.
- Add new schemas and examples for PRA/NSX/PRG, workflow hardening, weak seams, red-team/fix, and final proof artifacts.
- Register new artifact types in `contracts/standards-manifest.json`.
- Add/extend tests for deterministic loop behavior, workflow front-door coverage, and contract conformance.
- Update `docs/architecture/system_registry.md` with canonical PRA/NSX role definitions and preserved boundaries.
- Add delivery report at `docs/reviews/PRA-NSX-PRG-001_delivery_report.md`.

## Owner boundaries
- PRA: PR anchor resolution/normalization/impact extraction artifacts only.
- NSX: non-authoritative next-slice ranking, bottleneck, fragility, and recommendation records only.
- PRG: non-authoritative prompt generation and size governance only.
- CDE: authoritative execution mode selection only.
- CON/LIN/OBS/REP: authoritative gate-input audits and explainers in their domains.
- FRE: remediation expansion and rerun-lock artifacts; fix-pack artifacts in canonical FRE→TPA→SEL→PQX lane.
- SLH remains front-door enforcement, not planning.

## Roadmap steps implemented in this batch
1. Implement PRA records (resolution, normalization, anchor, changed scope, CI/review extraction, system impact, PR delta, review summary).
2. Implement SLH workflow-level enforcement + workflow coverage audits + rerun lock + remediation class expansion.
3. Implement weak-seam hardening artifacts (LIN-18, OBS-25, REP-18, CON-29).
4. Implement NSX ranking/bottleneck/fragility/safe-slice/fix-now-vs-later artifacts.
5. Implement PRG prompt-generation artifacts including size governor and plan-first skeleton.
6. Implement CDE execution mode selector artifact.
7. Implement red-team/fix artifact generation for PRA/SLH bypass and paired RT/FX rounds.
8. Emit final proof artifacts for PRA/NSX/PRG/workflow/rerun proofs.
9. Update registry + contracts/examples/manifest + tests + delivery report.

## Red-team rounds and paired fixes
- RIL-16 + FX-PRA-01: PRA/SLH bypass attempts.
- RT/FX PRA-02: wrong-PR selection / override confusion.
- RT/FX PRA-03: NSX overfitting to tiny local failures.
- RT/FX PRA-04: bloated prompt generation.
- RT/FX PRA-05: workflow front-door partial coverage.

## Validation commands
- Targeted:
  - `pytest -q tests/test_pra_nsx_prg_loop.py`
  - `pytest -q tests/test_shift_left_preflight.py`
  - `pytest -q tests/test_shift_left_hardening_superlayer.py`
- Contract surfaces:
  - `pytest -q tests/test_contracts.py`
  - `pytest -q tests/test_contract_enforcement.py`
  - `python scripts/run_contract_enforcement.py`
- Guardrails:
  - dependency graph validation path (`python scripts/build_dependency_graph.py`)
  - system registry guard (`python scripts/run_system_registry_guard.py`)
- Broad:
  - `pytest -q`

## Anti-scope-creep guardrails
- No SLH redesign: integrate workflow-level enforcement using existing SLH front door.
- No owner overlap: PRA/NSX/PRG boundaries remain explicit and non-authority where required.
- No unrelated refactors: limit edits to roadmap-required artifacts/scripts/tests/docs.
- Deterministic + fail-closed behavior only; no hidden network-only dependencies in tests.
