# PLAN — DASHBOARD-GUIDANCE-AND-POLISH-MASTER-02

## Prompt Type
PLAN

## Scope
Build the next operator dashboard guidance layer in strict serial order while remaining frontend-only and artifact-first.

## Constraints
- Frontend-only changes in dashboard UI and documentation.
- No backend/API routes, auth, charts, execution buttons, polling, or websocket behavior.
- Preserve artifact contracts and graceful failure behavior.
- Keep the surface calm, mobile-first, and explicit when data is missing.

## Serial Execution Plan
1. **Warning + freshness foundation**
   - Add warning banner gating logic from hard gate, constitution, drift, run status, fallback mode, staleness, and missing key artifact conditions.
   - Add refresh state badge (`Fresh`, `Stale`, `Fallback`, `Unknown`) derived from snapshot metadata.
   - Add simple staleness derivation from timestamp metadata when available.
2. **Next action guidance cluster**
   - Add a top clustered section with next action, confidence, explainability, and “what would change this recommendation”.
   - Enforce ordered decision policy: hard gate → blocked/repair run → bottleneck → deferred readiness → next governed cycle.
3. **Warnings + completeness surfaces**
   - Add a compact top warnings panel for active concerns.
   - Add data completeness panel with loaded/missing key artifacts and explicit recommendation degradation status.
4. **Integrity + change + path/provenance**
   - Add system integrity summary (execution, review, control, constitutional).
   - Add “What Changed Since Last Cycle” with honest history fallback when prior artifacts are unavailable.
   - Add critical path and decision provenance panels.
5. **Deferred/trends/caveats/readiness + polish**
   - Add deferred reactivation panel, textual trend strip, caveats section, and readiness-to-expand card with conservative logic.
   - Tighten card hierarchy/spacing, empty states, and object rendering robustness for mobile readability.
6. **Validation + review artifacts**
   - Run `npm install` and `npm run build` in `dashboard/`.
   - Write review findings and delivery report with limitations and non-goals.

## Risk Controls
- Treat `"Not available yet"` and missing fields as unavailable rather than valid evidence.
- Keep all artifact retrieval fail-closed to independent panel degradation.
- Avoid overstated confidence when history or key artifacts are missing.
