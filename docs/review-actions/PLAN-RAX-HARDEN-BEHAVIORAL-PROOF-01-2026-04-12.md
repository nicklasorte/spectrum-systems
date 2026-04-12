# PLAN — RAX-HARDEN-BEHAVIORAL-PROOF-01 (2026-04-12)

## Prompt type
BUILD

## Scope
Surgical hardening of roadmap realization behavioral-proof enforcement in `scripts/roadmap_realization_runner.py` and targeted tests in `tests/test_roadmap_realization_runner.py`.

## Execution steps
1. Define strict behavioral test policy classification (`behavioral`, `weak`, `invalid`) with explicit weak-pattern rejection and approved pytest target constraints.
2. Add behavioral integrity + coverage-binding validator that requires at least one behavioral target relevant to declared `target_modules`/`runtime_entrypoints`/`acceptance_checks`.
3. Enforce stronger verified gate than runtime_realized by requiring strict behavioral proof quality and no weak-only/ambiguous path.
4. Add regression tests for `string_match_only`, `non_behavioral_smoke_only`, mixed weak+irrelevant approved proof, and false-label/ambiguous proof rejection.
5. Run focused test suite for roadmap realization runner and summarize any remaining gaps.
