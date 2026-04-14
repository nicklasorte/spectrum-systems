# AUD-01 — Retroactive Pytest Integrity Audit

## Summary
AUD-01 adds a governed retroactive backtest capability that re-evaluates historical preflight artifacts for PYX-01 pytest execution authority compliance. The capability emits deterministic, schema-bound audit and remediation artifacts without mutating historical evidence.

## Methodology
1. Retrieve historical preflight artifacts from repo-local governed roots (`outputs/`, `artifacts/`, `data/`).
2. Normalize each artifact into a deterministic trust classification tuple:
   - classification
   - reason codes
   - context (`pr`, `non_pr`, `unknown`)
   - remediation recommendation
3. Apply PYX-01 backtest rules:
   - PR trust outcomes (`ALLOW`/`WARN`/`passed`) require authoritative `pytest_execution` truth from preflight-owned fields.
   - Missing or incomplete execution-truth fields are suspect.
   - Workflow/downstream pytest evidence is non-authoritative.
4. Emit:
   - `retroactive_pytest_integrity_audit_result`
   - bounded `retroactive_pytest_remediation_queue`

## Scan scope
- `**/contract_preflight_result_artifact.json`
- `**/contract_preflight_report.json`
- Restricted to repo-local scan roots only (no network, no external system scan).

## Trust limits
- The audit can only reason over persisted artifacts available in-repo.
- If context cannot be recovered (missing event shape), the run is classified `unable_to_evaluate` rather than trusted.
- This audit does not reconstruct git history or infer missing artifacts from workflow logs.

## False-positive / false-negative risks
### False positives
- Historical non-PR runs with partial fields may still appear suspect if they claim PR-style trust semantics.

### False negatives
- If non-authoritative workflow evidence is embedded in unrecognized custom fields, detection may miss it.
- Missing historical artifacts cannot be evaluated and are explicitly isolated as `unable_to_evaluate`.

## Operator usage
1. Run: `python scripts/run_retroactive_pytest_integrity_audit.py`
2. Review result artifact counts and reason-code summary.
3. Treat remediation queue as bounded worklist:
   - re-run governed preflight when commit-pair context is reconstructable
   - otherwise perform manual operator review
   - quarantine suspect runs from trusted baseline metrics until revalidated

## Determinism and fail-closed behavior
- Input traversal and output ordering are path-sorted.
- Queue size is explicitly bounded.
- Command exits non-zero only when audit execution invariants fail.
- Suspect findings are data outcomes, not process failures.

## Next operator step
Run this audit as part of governance health checks and triage queue items to close historical trust debt before using legacy run sets as baseline-quality evidence.
