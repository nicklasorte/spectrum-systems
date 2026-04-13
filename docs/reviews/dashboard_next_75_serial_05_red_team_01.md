# DASHBOARD-NEXT-75-SERIAL-05 Red Team Review 01

## Scope
Review of new coordination/intelligence surfaces for shadow-authority risk, hidden prioritization logic, overclaiming, and dashboard self-complexity.

## Blockers
1. Ranking panels needed explicit abstention when governed materiality evidence is missing.
2. Some observational surfaces needed an explicit uncertainty marker in blocked state summaries.

## Top 5 Surgical Fixes
1. Add ranking abstention guard keyed to governed `materiality_score`/`severity` only.
2. Add explicit uncertainty marker text in blocked diagnostics.
3. Keep all new surfaces read-only in capability map.
4. Keep source artifact and ownership visible in render rows.
5. Wire serial-05 regression tests for contract/capability/provenance/compiler parity.
