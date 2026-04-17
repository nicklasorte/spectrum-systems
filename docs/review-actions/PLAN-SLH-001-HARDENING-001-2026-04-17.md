# PLAN — SLH-001-HARDENING-001 (2026-04-17)

## Prompt Type
`BUILD`

## Intent
Harden existing SLH-001 implementation (PR #1103) into a fail-closed preflight control surface by replacing synthetic runner inputs with repository-derived signals, enforcing mandatory mini-cert dimensions, and blocking empty/missing manifest evidence.

## Seam Inspection Summary
- `spectrum_systems/modules/runtime/shift_left_hardening_superlayer.py`
  - `evaluate_manifest_strict_validation` currently permits empty contract input to pass.
  - `decide_pre_execution_certification` currently requires only a subset of critical dimensions.
- `scripts/run_shift_left_hardening_superlayer.py`
  - Builds most checks from hardcoded literals and synthetic pass stubs.
  - No change-aware scope derivation for preflight narrowing.
  - No deterministic path to use existing dependency graph and registry guard execution surfaces.
- `tests/test_shift_left_hardening_superlayer.py`
  - Covers baseline behavior but lacks explicit regression tests for synthetic-input bypass prevention, required mini-cert dimensions, and empty manifest fail-closed behavior.

## Review Findings Being Fixed
1. Synthetic guard runner (hardcoded pass literals).
2. Fail-open mini-certification when critical dimensions are omitted.
3. Empty manifest strict validation false pass.

## Files To Modify
1. `spectrum_systems/modules/runtime/shift_left_hardening_superlayer.py`
2. `scripts/run_shift_left_hardening_superlayer.py`
3. `tests/test_shift_left_hardening_superlayer.py`
4. `docs/reviews/SLH-001-HARDENING-001_delivery_report.md` (new)

## Repo-Derived Signal Computation Plan
- Load `contracts/standards-manifest.json` and feed real `contracts` entries into strict manifest evaluation.
- Resolve changed scope via explicit `--changed-files` or `git diff --name-only <base>..<head>`.
- Run dependency graph build (`scripts/build_dependency_graph.py`) and derive graph errors from process outcome and produced graph shape.
- Run system registry guard (`scripts/run_system_registry_guard.py`) with same changed scope and derive overlaps/authority violations from emitted reason codes.
- Derive:
  - eval signal from changed-file coverage against eval-related surfaces and explicit required eval test file presence.
  - context signal from missing governance anchors (`README.md`, `docs/architecture/system_registry.md`) and unresolved changed paths.
  - trace/observability signal from presence of output artifact and preflight reason chaining.
  - replay signal from deterministic changed-scope retrieval and git diff resolution status.
  - lineage signal from required manifest linkage fields.
  - hidden-state signal from disagreement between runner-computed and module-recomputed failure summaries.
- Fail closed whenever required evidence cannot be retrieved.

## Mini-Cert Required Dimension Enforcement Plan
- Expand required checks to include:
  - `sl_core`, `sl_structure`, `sl_memory`, `sl_router`, `sl_cert`, `dependency_graph`, `runtime_parity`, `eval`, `replay`, `lineage`, `observability`, `hidden_state`.
- Add deterministic reason-code semantics:
  - `missing_check:<name>`
  - `failed_check:<name>`
  - `missing_evidence:<name>`
  - `parity_weakness:<name>`

## Red-Team Rounds
1. **RT-H1 synthetic input bypass**
   - Force missing/invalid repo evidence paths and verify runner blocks.
2. **RT-H2 missing mini-cert dimensions**
   - Omit required dimensions in unit tests and verify fail-closed result with deterministic reason codes.
3. **RT-H3 empty manifest evidence**
   - Provide empty manifest contracts and verify strict validation fails with missing/empty evidence reason codes.

## Validation Commands
- `pytest -q tests/test_shift_left_hardening_superlayer.py`
- `pytest -q tests/test_contracts.py`
- `pytest -q tests/test_contract_enforcement.py`
- `python scripts/build_dependency_graph.py`
- `python scripts/run_system_registry_guard.py --changed-files scripts/run_shift_left_hardening_superlayer.py`
- `python scripts/run_contract_enforcement.py`
- `python scripts/run_shift_left_hardening_superlayer.py --output outputs/shift_left_hardening/superlayer_result.json --changed-files scripts/run_shift_left_hardening_superlayer.py tests/test_shift_left_hardening_superlayer.py`
- `pytest -q`
