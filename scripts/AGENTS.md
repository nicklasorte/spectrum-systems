# AGENTS.md — scripts/

## Ownership
Automation scripts — validation, scaffolding, graph generation, and review tooling.
Scripts are invoked directly (CLI) or by CI workflows in `.github/workflows/`.

## Local purpose
Provide deterministic, rerunnable automation for governance enforcement, module validation, contract auditing, and review preparation.
Scripts are not library code. They are standalone executables with clear inputs and outputs.

## Constraints
- **Idempotent behavior**: Scripts must be safe to run multiple times. Running a script twice must not corrupt data or double-count results.
- **No silent failures**: Scripts must exit non-zero on errors. CI gates depend on exit codes.
- **Output to stdout or declared files**: Scripts must not write to undeclared locations. Output paths must be configurable or clearly documented.
- **No production data**: Scripts must not connect to external APIs, databases, or live systems without explicit flags and documentation.
- **Minimal dependencies**: Prefer Python stdlib. Add third-party imports only if strictly necessary and documented.

## Required validation surface
Before adding or modifying a script:
1. Verify the script exits 0 on a clean repository state.
2. Verify the script exits non-zero when the targeted condition is violated.
3. If the script is called from CI, verify the corresponding workflow in `.github/workflows/` still passes.

## Files that must not be changed casually
| File | Reason |
| --- | --- |
| `scripts/run_contract_enforcement.py` | Primary contract enforcement runner — CI depends on its exit code |
| `scripts/validate_module_architecture.py` | Module boundary enforcement — CI gate depends on this |
| `scripts/validate_orchestration_boundaries.py` | Cross-module boundary validation — changing loosens architectural guardrails |
| `scripts/scaffold_governed_repo.py` | Repo scaffolding — changes affect all downstream repo initialization |

## Nearby files (read before editing)
- `.github/workflows/` — CI workflows that call these scripts
- `contracts/standards-manifest.json` — version pins referenced by enforcement scripts
- `docs/module-manifests/` — module boundary definitions referenced by validation scripts
- `AGENTS.md` (root) — operating rules that apply to all script changes
