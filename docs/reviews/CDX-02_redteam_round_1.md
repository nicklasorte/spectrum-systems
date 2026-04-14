# CDX-02 Red Team Round 1

## Scope
CHX adversarial checks over CTX, EVL, JDG, JSX, PRX, CRS, REL seams using deterministic fixtures and runtime validators.

## Findings
1. Stale active-set judgments could remain marked active without explicit rejection in lightweight runtime helpers.
2. Precedent retrieval needed explicit active+in-scope filtering defaults.
3. CRS scope needed tighter non-authority wording to prevent authority bleed.

## Fixes Applied
- Added `validate_jsx_active_set` stale-active rejection output.
- Added `retrieve_prx_precedents` active/in-scope filtering behavior.
- Narrowed CRS registry role/must-not boundaries.

## Status
Round 1 findings converted to code and regression tests in this change set.
