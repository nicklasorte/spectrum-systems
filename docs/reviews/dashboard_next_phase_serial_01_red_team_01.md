# Dashboard Next Phase Serial 01 — Red Team Review 1

## Focus
- Trust-boundary breaches
- Provenance overclaiming
- Hidden selector-side decision logic
- Ownership overlap risk
- Certification and ledger confidence inflation

## Findings
### Blockers
1. Certification gate was not previously wired to runtime render path.
2. Panel ownership/provenance contracts were not exhaustive for next-phase panels.

### Top 5 surgical fixes
1. Add explicit surface contract registry and capability map.
2. Add field-level provenance map and consume in read-model compiler.
3. Add contract-backed status normalization with unknown fail-closed handling.
4. Add dashboard certification gate validation.
5. Render blocked diagnostics for all added operator panels.

## Repair handoff
Apply only blocker/top-5 fixes above before additional breadth.
