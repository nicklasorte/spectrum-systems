# PLAN-RDX-EXEC-03-UMBRELLA-04-2026-04-10

## Prompt type
PLAN

## Intent
Execute the RDX-EXEC-03 umbrella stress test in governed serial mode and publish deterministic artifacts/reviews proving BRF enforcement, fail-closed progression control, and mandatory red-team verification.

## Scope
1. Create canonical execution trace artifact for four-umbrella serial run.
2. Create mandatory red-team review `docs/reviews/RVW-RDX-EXEC-03-UMBRELLA-04.md`.
3. Create mandatory delivery report `docs/reviews/BATCH-RDX-EXEC-03-UMBRELLA-04-DELIVERY-REPORT.md`.

## Files
- `artifacts/rdx_runs/BATCH-RDX-EXEC-03-UMBRELLA-04-artifact-trace.json` (CREATE)
- `docs/reviews/RVW-RDX-EXEC-03-UMBRELLA-04.md` (CREATE)
- `docs/reviews/BATCH-RDX-EXEC-03-UMBRELLA-04-DELIVERY-REPORT.md` (CREATE)

## Validation
1. `pytest`
2. `python scripts/run_review_artifact_validation.py --repo-root . --output-json /tmp/review_validation_rdx_exec03.json --allow-full-pytest`
3. `python scripts/run_contract_preflight.py --changed-path docs/reviews/RVW-RDX-EXEC-03-UMBRELLA-04.md --changed-path docs/reviews/BATCH-RDX-EXEC-03-UMBRELLA-04-DELIVERY-REPORT.md --changed-path artifacts/rdx_runs/BATCH-RDX-EXEC-03-UMBRELLA-04-artifact-trace.json --output-dir outputs/contract_preflight_rdx_exec03`

## Guardrails
- Enforce serial hierarchy `slice → batch → umbrella` with cardinality minimums.
- Mark all batch/umbrella decisions as progression-only.
- Preserve CDE-exclusive authority boundaries for closure/readiness/promotion.
- Stop on any missing artifact, invalid lineage, review omission, governance overdue risk, or contract violation.
