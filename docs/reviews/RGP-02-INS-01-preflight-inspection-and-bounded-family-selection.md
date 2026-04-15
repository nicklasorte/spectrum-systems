# RGP-02 INS-01 — preflight inspection and bounded artifact-family selection

## STEP INS-01 — inspect repo seams and choose bounded artifact family
Owner: TLC + non-authoritative

Build:
- schema:
  - No new inspection schema added; repository already uses markdown review artifacts under `docs/reviews/`.
- functionality:
  - Located canonical system registry markdown: `docs/architecture/system_registry.md`.
  - Located machine-readable system registry: `ecosystem/system-registry.json` and schema `ecosystem/system-registry.schema.json`.
  - Located standards manifest: `contracts/standards-manifest.json`.
  - Located schema/examples directories: `contracts/schemas/` and `contracts/examples/`.
  - Located runtime module layout: `spectrum_systems/` and `control_plane/` packages, plus governed execution scripts under `scripts/`.
  - Located preflight/certification/promotion seams: `scripts/run_contract_preflight.py`, `docs/runtime/closure_decision_engine.md`, `scripts/run_control_loop_certification.py`, `scripts/run_release_canary.py`.
  - Located existing seams for eval/routing/context/judgment/replay/observability/drift/handoff/policy/release/calibration/override/queue/cost/guardrails via contracts in `contracts/schemas/` and tests under `tests/`.
  - Located existing test and review artifact patterns: `tests/test_contracts.py`, `tests/test_contract_enforcement.py`, and `docs/reviews/*.md`.
- integration:
  - Extension points selected:
    - contracts: `contracts/schemas/*`, `contracts/examples/*`, `contracts/standards-manifest.json`
    - runtime validator seam: `spectrum_systems/governance/`
    - tests: `tests/`
- control/eval:
  - Bounded artifact family selected: **governed_prompt_queue** (existing governed path with contract, preflight, gating, and canary seams).
- tests:
  - Inspection-only step; no executable test changes.

Definition of done:
- This inspection artifact exists.
- Canonical registry files identified.
- Bounded artifact family explicitly named.
- No-go boundaries documented:
  - No new authority owner introduction.
  - CDE remains sole closure/promotion authority.
  - TPA remains policy admissibility authority.
  - SEL remains enforcement authority.
  - Preparatory and analytical artifacts remain non-authoritative.
