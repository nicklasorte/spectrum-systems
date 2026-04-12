# Dashboard Next Phase Serial 03 — Red Team Review 01

## Prompt type
REVIEW

## Scope
DASH-01 through DASH-30 implementation surfaces for governed dashboard expansion.

## Findings
### Blockers
1. Missing explicit panel contracts for policy visibility, audit trail, non-decision action surface, review queue surface, and misinterpretation guard.
2. Read-model lacked explicit fail-closed uncertainty guard when freshness/replay disagreement exists.
3. Review queue/action traces were present in UI but not encoded as operator panel contracts/capability/provenance entries.

### Top 5 surgical fixes
1. Add missing contracts to `surface_contract_registry.ts` with ownership/render/freshness/provenance requirements.
2. Add matching read-only entries to `panel_capability_map.ts`.
3. Add field-level provenance rows for all new panels.
4. Wire fail-closed compiler logic for policy/audit/action/review surfaces.
5. Add a misinterpretation guard panel that blocks on disagreement/low evidence and forces explicit uncertainty labels.

## Non-blockers
- Existing serial-01/02 certification gate integrity remains preserved.
- No shadow decision authority found in capability map.
