# PLAN — BATCH-AUT-REG-05A (2026-04-10)

Prompt type: BUILD

## Scope
Deepen weak slice families in `contracts/roadmap/slice_registry.json` only for:
- AEX-01, AEX-02
- AUT-01..AUT-10
- SVA-ADV/DRIFT/LOAD/REC-01..04
- UMB-DEC-01

Also update fail-closed quality checks + targeted tests, add missing fixture artifacts needed by revised first commands, and produce required review/delivery docs.

## Steps
1. Inspect repo-native seams (AEX admission, AUT autonomy, SVA stress-class, umbrella progression) and available fixture paths.
2. Add minimal realistic fixtures under canonical fixture/example paths for any missing artifact-driven commands in scope.
3. Surgically update scoped slice first commands + implementation notes to target real/proxied repo-native seams and honest partials where needed.
4. Strengthen `roadmap_slice_registry` weak-family validation rules (generic helper ban, toy inline payload pressure, per-family first-command diversity + seam-note requirements).
5. Add/adjust targeted tests for new weak-family checks and fixture-backed command loading.
6. Run targeted test suite for touched surfaces + slice registry gates.
7. Author `docs/reviews/RVW-BATCH-AUT-REG-05A.md` and `docs/reviews/BATCH-AUT-REG-05A-DELIVERY-REPORT.md`.
8. Commit changes and open PR via `make_pr`.
