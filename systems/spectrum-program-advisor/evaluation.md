# Spectrum Program Advisor — Evaluation (SYS-005)

## Evaluation Goals
- Verify decision readiness scoring is deterministic and traceable to blockers.
- Ensure outputs validate against canonical contracts and reference required risk categories.
- Confirm dependency-aware milestone status is reflected in readiness gating.
- Check missing-evidence reporting when artifacts are stale or absent.

## Assets
- Fixtures: `examples/spectrum-program-advisor/examples/inputs/` and `.../outputs/`.
- Contracts: `contracts/schemas/program_brief.schema.json`, `study_readiness_assessment.schema.json`, `next_best_action_memo.schema.json`, `decision_log.schema.json`, `risk_register.schema.json`, `assumption_register.schema.json`, `milestone_plan.schema.json`.

## Test Matrix
- **Schema validation**: Validate all generated artifacts against contracts; fail on additional properties or missing links.
- **Determinism**: Re-run advisor on identical fixtures and compare structured outputs byte-for-byte.
- **Dependency handling**: Mutate milestone dependency status in fixtures; readiness must track the least-ready dependency.
- **Risk category coverage**: Ensure all risk entries use canonical categories and surface category coverage in summaries.
- **Traceability**: Assert every decision, risk, and action in outputs includes `source_artifacts` or `source_reference` links back to inputs.
- **Missing artifacts**: Remove an input (e.g., minutes metadata) and confirm missing-evidence report captures it and readiness score drops.

## Metrics
- Readiness score stability across runs.
- Coverage of required risk categories.
- Count of unresolved decisions vs. decision readiness thresholds.
- Latency from input change to readiness delta (tracked in evaluation logs).

## Review Gates
- Human review of readiness gating logic and blocker lists.
- Human approval of generated memos before distribution.

## Tooling
- Prefer contract validation utilities in `spectrum_systems.contracts`.
- Downstream repo should add regression tests exercising CLI commands against fixtures; this repo ships scaffolded tests in `examples/spectrum-program-advisor/tests`.
