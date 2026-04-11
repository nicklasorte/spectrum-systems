# PLAN — DASHBOARD-SNAPSHOT-01

- **Prompt Type:** PLAN
- **Batch:** DASHBOARD-SNAPSHOT-01
- **Umbrella:** REPO_OBSERVABILITY_LAYER
- **Date:** 2026-04-10

## Scope
Build a deterministic, repo-native snapshot generator that emits `artifacts/dashboard/repo_snapshot.json` using filesystem inventory and simple heuristics aligned to the live dashboard contract.

## Execution Steps
1. Create `scripts/generate_repo_dashboard_snapshot.py` with deterministic repository scanning, compact contract emission, and `--output` support.
2. Create `tests/test_generate_repo_dashboard_snapshot.py` to validate contract shape, output creation, deterministic list ordering, non-negative counts, custom output path support, and behavior with optional directories absent.
3. Run required validation commands and generate `artifacts/dashboard/repo_snapshot.json`.
4. Create `docs/reviews/RVW-DASHBOARD-SNAPSHOT-01.md` with verdict and answers to required review questions.
5. Create `docs/reviews/DASHBOARD-SNAPSHOT-01-DELIVERY-REPORT.md` with files created, contract confirmation, validations, output location, and explicit v1 non-goals.

## Determinism and Failure Rules
- Deterministic ordering for emitted arrays and hotspot groups.
- UTC ISO-8601 timestamp in `generated_at` only.
- Fail closed on output-path or serialization failure (non-zero exit).
- Ignore cache/temp directories (`.git`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.venv`, `node_modules`, etc.).

## Out of Scope
- No dashboard contract redesign.
- No generic analytics framework.
- No prompt-driven logic.
- No unrelated refactors.
