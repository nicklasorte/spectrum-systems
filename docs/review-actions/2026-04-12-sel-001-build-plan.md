# SEL-001 Build Plan (Primary Type: BUILD)

- **Batch:** SEL-001
- **Mode:** SERIAL + IMPLEMENTATION-REQUIRED + ADVERSARIAL + REPO-NATIVE
- **Date:** 2026-04-12

## Ordered execution plan
1. **CDE-10 closeout gate:** verify CDE decision flow is operational in real repository paths and add a closeout gate artifact + tests if missing.
2. **SEL-01 contracts:** add schema-bound SEL artifacts (`enforcement_action_record`, `enforcement_result_record`, `enforcement_eval_result`, `enforcement_readiness_record`, `enforcement_conflict_record`, `enforcement_effectiveness_record`, `enforcement_bundle`) with examples and standards-manifest entries.
3. **SEL-02 to SEL-08 implementation:** add deterministic SEL enforcement foundation module that:
   - fences upstream/downstream boundaries,
   - maps bounded actions deterministically,
   - evaluates enforcement artifacts,
   - enforces candidate-only readiness,
   - validates decision-to-enforcement integrity,
   - validates replay determinism,
   - computes effectiveness tracking.
4. **Built-in red-team loop (RT1-RT5 + FX1-FX5):** encode adversarial fixtures and fail-closed assertions directly in eval-style tests; harden module logic for every discovered exploit and add permanent regressions.
5. **Validation & closeout:** run contract/schema enforcement and targeted runtime tests for CDE + SEL seams.

## Scope controls
- Keep CLIs thin; enforce behavior in runtime modules.
- Keep changes bounded to CDE/SEL contracts, runtime modules, tests, and standards manifest.
- Preserve canonical boundaries: CDE decides, SEL enforces bounded actions only, promotion remains separately gated.
