# AGL-01 Fix Actions (PLAN)

## AEX Admission Step
- Request type: BUILD
- Intended outcome: Add strict artifact-backed agent core loop proof artifacts for Codex/Claude repo-mutating work and wire rollup/dashboard/test coverage.
- Changed surfaces:
  - `contracts/schemas/` (new schema)
  - `contracts/examples/` (new examples)
  - `contracts/standards-manifest.json` (registration)
  - `spectrum_systems/modules/runtime/` (builder)
  - `scripts/` (CLI)
  - `artifacts/dashboard_metrics/` (rollup artifact wiring)
  - `tests/` and `apps/dashboard-3ls/__tests__/` (validation)
  - `docs/reviews/` and this file (red-team/final report/traceability)
- Authority-shape risks:
  - Accidentally giving MET CDE-signal authority (must remain observation-only)
  - Implicit evidence inference from free text (must require artifact refs)
  - Overstating AEX/PQX/EVL/TPA/CDE/SEL ownership language outside canonical registry
- Required tests/evals:
  - Contract validation + targeted pytest for agent loop/ai_programming/governance
  - Dashboard tests in `apps/dashboard-3ls`
  - Authority preflight command
- Required schema/artifact updates:
  - New `agent_core_loop_run_record` schema + examples + manifest entry
  - Generated artifacts in `artifacts/agent_core_loop/`
  - Rollup artifact includes core loop refs and counts
- Governance mappings required:
  - Ensure ai programming rollup references only artifact-backed status
  - Preserve `authority_scope: observation_only`
- Replay/observability updates:
  - Include `replay_refs` and `trace_refs`; emit unknown/missing with reason codes
- Scope split check:
  - Scope is large but coherent under single AGL-01 governed artifact; proceed as one slice.

## Must-fix findings
- Pending red-team execution.
