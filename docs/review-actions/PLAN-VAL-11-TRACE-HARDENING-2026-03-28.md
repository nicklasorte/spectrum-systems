# Plan — VAL-11 Trace Linkage Hardening — 2026-03-28

## Prompt type
PLAN

## Roadmap item
VAL-11 — Certification Integrity (defect fix)

## Objective
Harden DONE-01 so certification fails closed on missing, ambiguous, or inconsistent cross-artifact trace linkage, and close VAL-11 case F false-pass.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-VAL-11-TRACE-HARDENING-2026-03-28.md | CREATE | Required plan artifact for multi-file defect fix. |
| PLANS.md | MODIFY | Register active VAL-11 hardening plan. |
| spectrum_systems/modules/governance/done_certification.py | MODIFY | Add explicit cross-artifact trace-linkage validation and auditable check result. |
| contracts/schemas/done_certification_record.schema.json | MODIFY | Add explicit trace_linkage check result contract field. |
| contracts/examples/done_certification_record.json | MODIFY | Keep example aligned with updated schema. |
| contracts/standards-manifest.json | MODIFY | Bump standards manifest and update done_certification_record contract version metadata. |
| tests/test_done_certification.py | MODIFY | Add required trace-linkage failure coverage. |
| tests/test_certification_integrity.py | MODIFY | Assert VAL-11 case F now fails directly and no false certification remains. |

## Contracts touched
- `contracts/schemas/done_certification_record.schema.json` (add trace_linkage check result).
- `contracts/standards-manifest.json` (version metadata update for done_certification_record).

## Tests that must pass after execution
1. `pytest tests/test_done_certification.py`
2. `pytest tests/test_certification_integrity.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_contract_enforcement.py`
5. `python scripts/run_contract_enforcement.py`
6. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign DONE-01 gating semantics.
- Do not introduce alternate certification paths.
- Do not add fuzzy/inferred trace matching rules.

## Dependencies
- Existing DONE-01 and VAL-11 seams remain authoritative and must be exercised directly.
