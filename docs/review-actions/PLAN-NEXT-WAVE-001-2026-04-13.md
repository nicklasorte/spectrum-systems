# PLAN — NEXT-WAVE-001 (2026-04-13)

## Primary prompt type
BUILD

## Scope
Implement repo-native governance additions for JDX, RUX, XPL, REL, DAG, EXT plus MNT enforcement wiring artifacts, with deterministic runtime modules, contract schemas/examples, registry updates, and tests.

## Execution sequence
1. Inspect existing contracts/runtime/tests and reuse established deterministic/fail-closed patterns.
2. Update `docs/architecture/system_registry.md` and registry boundary validator for new canonical systems.
3. Add contracts (schemas/examples) for JDX/RUX/XPL/REL/DAG/EXT + MNT-25..29 enforcement artifacts.
4. Update `contracts/standards-manifest.json` with new contract entries and version bumps.
5. Implement runtime modules:
   - `jdx_runtime.py`
   - `rux_runtime.py`
   - `xpl_runtime.py`
   - `rel_runtime.py`
   - `dag_runtime.py`
   - `ext_runtime.py`
   - `mnt_enforcement_runtime.py`
6. Add deterministic tests for contracts and runtime behavior, including exploit-to-guard regression checks.
7. Run required validation commands and targeted tests.
8. Commit and generate PR message.

## Constraints
- Artifact-first execution, fail-closed behavior, promotion requires certification.
- No hidden authority creep; new layers remain non-authoritative where required.
- No unrelated refactors.
