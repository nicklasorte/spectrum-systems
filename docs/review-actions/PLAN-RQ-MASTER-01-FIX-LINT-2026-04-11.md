# PLAN — RQ-MASTER-01-FIX-LINT

- **Prompt Type:** BUILD
- **Batch:** RQ-MASTER-01-FIX-LINT
- **Umbrella:** OPERATOR_TRUTH_AND_DECISION_QUALITY
- **Date:** 2026-04-11

## Scope
Apply a surgical, non-interactive lint fix for the Next.js dashboard by adding explicit ESLint config and required lint dependencies.

## Steps
1. Update `dashboard/package.json` to add `eslint` and `eslint-config-next` in `devDependencies` while preserving the existing `lint` script (`next lint`).
2. Create `dashboard/.eslintrc.json` with the exact required `next/core-web-vitals` extension.
3. Run `cd dashboard && npm install && npm run lint` to verify lint executes without interactive setup prompts.
4. Create review and delivery report artifacts documenting validation outcome and CI behavior impact.

## Constraints
- No dashboard runtime/UI behavior changes.
- No Next.js config redesign.
- No interactive setup paths.
