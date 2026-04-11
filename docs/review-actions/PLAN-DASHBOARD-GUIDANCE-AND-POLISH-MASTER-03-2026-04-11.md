# PLAN — DASHBOARD-GUIDANCE-AND-POLISH-MASTER-03

Primary type: PLAN
Date: 2026-04-11
Batch: DASHBOARD-GUIDANCE-AND-POLISH-MASTER-03
Umbrella: REPO_OBSERVABILITY_LAYER
Execution mode: SERIAL

## Scope
Frontend-only dashboard execution for tooling seam hardening and operator guidance polish in `dashboard/`.

## Serial execution steps
1. **Tooling seam fixes first**
   - Update `dashboard/package.json` scripts to include `lint` and verify required TypeScript dev dependencies are explicit.
   - Verify TypeScript app-router support files exist and are sane:
     - `dashboard/tsconfig.json`
     - `dashboard/next-env.d.ts`
     - `dashboard/app/layout.tsx`

2. **Operator guidance upgrade in dashboard surface**
   - Implement and/or harden warning banner, refresh badge, staleness logic.
   - Ensure next action includes confidence, why, and what would change recommendation.
   - Ensure top warnings, data completeness, system integrity summary, change summary, critical path, decision provenance, deferred reactivation, trend strip, caveats, and readiness-to-expand panels are present and graceful under missing artifact conditions.
   - Keep mobile-first readability and calm visual hierarchy.

3. **Validation sequence**
   - Run:
     - `cd dashboard && npm install`
     - `cd dashboard && npm run lint`
     - `cd dashboard && npm run build`
   - Confirm no `[object Object]` rendering paths remain in structured object areas.

4. **Review and delivery artifacts**
   - Create:
     - `docs/reviews/RVW-DASHBOARD-GUIDANCE-AND-POLISH-MASTER-03.md`
     - `docs/reviews/DASHBOARD-GUIDANCE-AND-POLISH-MASTER-03-DELIVERY-REPORT.md`
   - Capture what is complete, what degraded gracefully, and what remains intentionally out of scope.
