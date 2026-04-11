# PLAN — DASHBOARD-POLISH-MASTER-01

## Prompt Type
PLAN

## Scope
Upgrade the dashboard frontend into a mobile-first operator control surface without changing backend routes, artifact contracts, or execution model.

## Constraints
- Frontend only (`dashboard/app/*`, `dashboard/components/*`).
- No auth, charts, execution buttons, polling, or websocket behavior.
- Preserve static JSON retrieval from public paths.
- Fail gracefully when artifacts are missing or malformed.
- Preserve Vercel deployability and Next.js build stability.

## Execution Steps
1. **Layout hardening**
   - Normalize `dashboard/app/layout.tsx` to minimal valid root layout with `globals.css`.
   - Confirm `dashboard/app/page.tsx` renders one `RepoDashboard` instance.
   - Establish a stable global baseline in `dashboard/app/globals.css` for mobile-safe rendering.
2. **Dashboard structure + hierarchy**
   - Refactor `dashboard/components/RepoDashboard.tsx` to remove brittle layout patterns and provide calm card hierarchy.
   - Add an explicit top summary flow with clear title/subtitle and operator-focused pacing.
3. **Operator guidance additions**
   - Add **Next Action** panel with priority logic sourced from hard gate, run state, bottleneck, deferred readiness, and drift.
   - Add **System Health** and **What Changed** cards with truthful status derivation and history-safe fallback.
4. **Panel quality upgrades**
   - Improve all existing panels for readability, value hierarchy, empty-state consistency, and mobile-first spacing.
   - Ensure `runtime_hotspots` and `operational_signals` render as structured objects, never raw object strings.
5. **Validation + reporting**
   - Run `npm install` and `npm run build` under `dashboard/`.
   - Record review findings in `docs/reviews/RVW-DASHBOARD-POLISH-MASTER-01.md`.
   - Record delivery details in `docs/reviews/DASHBOARD-POLISH-MASTER-01-DELIVERY-REPORT.md`.

## Risk Controls
- Keep all artifact retrieval wrapped in safe parse/error handling.
- Ensure one artifact failure does not block others.
- Default to standardized copy when data/history is unavailable.
