# SEL-002 / RQX-02 Build Plan (Primary Type: BUILD)

- **Batch:** SEL-002
- **Mode:** SERIAL + IMPLEMENTATION-REQUIRED + REPO-NATIVE + ADVERSARIAL
- **Date:** 2026-04-12

## Ordered execution plan
1. **SEL-09 runner:** add a deterministic SEL orchestration runner module + thin CLI that consumes governed CDE artifacts and emits a full SEL artifact chain in run directories.
2. **SEL-10 flow wiring:** wire runner outputs into repo-native execution flow surfaces and add fail-closed missing-input behavior.
3. **SEL-11 replay gate:** add CI-consumable replay validation for the real SEL runner path and fail closed on replay mismatch or incomplete evidence.
4. **SEL-12 chain validation:** add production artifact-chain validation (presence + trace + lineage + schema) for SEL runner outputs.
5. **SEL-13 audit stabilization:** tighten contract-boundary audit reporting for SEL-relevant surfaces by classifying known legacy warnings without suppressing real failures.
6. **RQX-01 foundation:** add bounded red-team orchestration contracts + runtime module to execute rounds and emit governed findings/fix requests/closure requests.
7. **RQX-02 owner routing:** implement explicit finding→owner routing with fail-closed ambiguous handling and operator handoff emission.
8. **RQX-03 closure proof gate:** require closure proof artifacts (eval + regression + hardening + linkage) before finding closure can pass.

## Scope controls
- Keep CLIs thin and keep decision/routing/verification logic in runtime modules.
- Preserve bounded ownership: RQX orchestrates review/fix-request/closure-verification only; SEL enforces only.
- Reuse existing contract loader, schema validation, trace linkage, and deterministic hashing patterns.
