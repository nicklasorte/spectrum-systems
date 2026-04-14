# PYX-02 — PR Pytest Execution Path Review

## Scope inspected
- `.github/workflows/artifact-boundary.yml`
- `.github/workflows/pr-autofix-contract-preflight.yml`
- `scripts/run_contract_preflight.py`
- `scripts/run_github_pr_autofix_contract_preflight.py`
- `spectrum_systems/modules/runtime/github_pr_autofix_contract_preflight.py`
- `spectrum_systems/modules/runtime/test_inventory_integrity.py`

## Live pull_request workflow path
1. `artifact-boundary.yml` triggers on `pull_request`.
2. Job `contract-preflight` runs `scripts/build_preflight_pqx_wrapper.py` then `scripts/run_contract_preflight.py`.
3. If first pass blocks and auto-repair is eligible, same job runs `scripts/run_github_pr_autofix_contract_preflight.py` (which reruns preflight).
4. `contract-preflight` currently checks `contract_preflight_result_artifact.json` and only enforces `pytest_execution.pytest_execution_count >= 1` for `ALLOW/WARN` outcomes.
5. Separate job `run-pytest` runs direct `pytest` but is explicitly non-authoritative redundancy; trust authority is preflight artifact.

## Where pytest is executed
- Not directly in the preflight workflow step shell.
- Indirectly inside `scripts/run_contract_preflight.py` through `run_targeted_pytests(...)`.
- Fallback PR targets are run in preflight when no deterministic target selection exists.

## Is `scripts/run_contract_preflight.py` in the live PR path?
Yes. It is in the canonical `artifact-boundary.yml` pull_request path and is the trust authority surface used by downstream checks.

## Current gap (pre-fix)
- Workflow-level guard only verifies `pytest_execution_count` from preflight artifact.
- There is no dedicated schema-bound pytest execution evidence artifact with executed flag, per-command exit accounting, or explicit failure reason.
- This allows “report-only” trust interpretation risk: a thin count field can be present without strong evidence semantics (artifact existence + authoritative execution accounting contract).

## Exact root cause of “PR had no pytest”
The enforcement seam relied on coarse `pytest_execution_count` signaling rather than a strict preflight-owned pytest execution evidence artifact and invariant checks. That left a trust gap where audit/reporting hardening could land without fully hard-failing all missing-or-non-authoritative execution evidence states in the canonical PR gate.
