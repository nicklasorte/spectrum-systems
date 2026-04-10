# PLAN-BATCH-RDX-AUT-03-2026-04-10

## Prompt type
VALIDATE

## Intent
Run one minimal-prompt governed execution pass where sequencing is retrieved from `contracts/roadmap/roadmap_structure.json` and slice execution behavior is retrieved from `contracts/roadmap/slice_registry.json`, with automatic fail-closed enforcement and review/fix gating evidence.

## Scope
1. Retrieve canonical roadmap artifacts and select the next valid umbrella using structure-only sequencing.
2. Execute real slice commands from slice metadata through PQX-owned execution flow.
3. Record automatic RQX review trigger behavior, TPA fix-gate behavior, and SEL fail-closed enforcement.
4. Emit progression-only `batch_decision_artifact` and `umbrella_decision_artifact` evidence.
5. Produce mandatory review and delivery report artifacts for BATCH-RDX-AUT-03.

## Files
- `artifacts/rdx_runs/BATCH-RDX-AUT-03-artifact-trace.json` (CREATE)
- `docs/reviews/RVW-BATCH-RDX-AUT-03.md` (CREATE)
- `docs/reviews/BATCH-RDX-AUT-03-DELIVERY-REPORT.md` (CREATE)

## Validation commands
1. `pytest tests/test_execution_hierarchy.py tests/test_roadmap_slice_registry.py -q`
2. `python scripts/run_contract_preflight.py --changed-path docs/review-actions/PLAN-BATCH-RDX-AUT-03-2026-04-10.md --changed-path artifacts/rdx_runs/BATCH-RDX-AUT-03-artifact-trace.json --changed-path docs/reviews/RVW-BATCH-RDX-AUT-03.md --changed-path docs/reviews/BATCH-RDX-AUT-03-DELIVERY-REPORT.md`
3. `python scripts/run_review_artifact_validation.py --repo-root .`
