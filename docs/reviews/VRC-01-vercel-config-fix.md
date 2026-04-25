# VRC-01 vercel config fix

## Prompt type
BUILD

## Issue
Vercel deployment failed with `Invalid request: should NOT have additional property "projectSettings"`.

## Fix
- Removed unsupported `projectSettings` from repository `vercel.json`.
- Preserved Vercel Root Directory expectation as `apps/dashboard-3ls` via deployment runbook expectations rather than unsupported JSON fields.
- Kept dashboard truth safeguards intact in `apps/dashboard-3ls/next.config.js`, including:
  - `REPO_ROOT` deployment expectation
  - `outputFileTracingRoot`
  - `outputFileTracingIncludes` for `../../artifacts/**/*`

## Validation
- `cd apps/dashboard-3ls && npm run build`
- `cd apps/dashboard-3ls && npm run test`

Deployment can now be retried with a Vercel-compatible configuration payload.
