# PLAN — OSX-03 RAX Serial Build (BUILD)

## Scope
Bounded artifact family: `prompt_task_bundle`.

## Execution plan
1. Inspect canonical registry, contracts, runtime seams, and gating seams.
2. Add missing OSX-03 schemas/examples and register them in `contracts/standards-manifest.json`.
3. Harden CTX/TLX runtime helpers to match required function contracts and fail-closed behavior.
4. Add bounded-runtime modules for DAT/DRT/ENT/HND + rollout gating + end-to-end serial runner.
5. Add over-testing suite for contract conformance, fail-closed behavior, red-team regressions, and end-to-end canary path.
6. Produce all required phase review and red-team artifacts including immediate fixes rounds.
7. Run contract + module tests and produce final QA sweep + delivery report.
