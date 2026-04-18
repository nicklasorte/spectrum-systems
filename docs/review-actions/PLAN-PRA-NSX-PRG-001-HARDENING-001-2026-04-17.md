# PLAN-PRA-NSX-PRG-001-HARDENING-001-2026-04-17

Primary Prompt Type: BUILD

## Review findings addressed
1. PR resolution failure path emits non-schema payload.
2. Workflow audit misses `.yaml` files.
3. PR delta compares incompatible artifact shape (`previous_anchor.impacted_systems`).
4. Repo-name inference uses unsafe `rstrip(".git")`.

## Exact files to modify
- `scripts/run_pra_nsx_prg_automation.py`
- `spectrum_systems/modules/runtime/pra_nsx_prg_loop.py`
- `tests/test_pra_nsx_prg_loop.py`
- `docs/reviews/PRA-NSX-PRG-001-HARDENING-001_delivery_report.md`

## Contract impact summary
- Add companion failure contract `pra_pull_request_resolution_failure_record` to keep `pra_pull_request_resolution_record` semantics strict while making fail-closed errors schema-valid.

## Test additions
- PR resolution failure emits schema-valid artifact for empty PR list.
- PR override mismatch emits schema-valid artifact.
- `.yaml` workflow files are included in workflow audit.
- Delta comparison supports compatible prior artifacts and fails closed on incompatible previous artifact input.
- Repo-name parsing tests for SSH/HTTPS `.git`, no suffix, and `widget` ending.

## Validation commands
- `pytest -q tests/test_pra_nsx_prg_loop.py`
- `pytest -q tests/test_shift_left_preflight.py`
- `pytest -q tests/test_contracts.py`
- `pytest -q tests/test_contract_enforcement.py`
- `python scripts/run_contract_enforcement.py`
- `python scripts/build_dependency_graph.py`
- `pytest -q`

## Fail-closed behavior expectations
- PR resolution failure returns exit 1 and writes schema-valid failure artifact.
- Incompatible `--previous-anchor` artifact returns exit 1 with explicit incompatibility reason.
- Workflow audit treats uncovered `.yml`/`.yaml` paths as blocking (`fail`).
