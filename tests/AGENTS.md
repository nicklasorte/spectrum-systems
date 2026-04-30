# AGENTS.md — tests/

## Ownership
Test surface — deterministic validation of contracts, modules, governance artifacts, and lifecycle behavior.
All tests in this directory are authoritative. Do not remove or disable tests without explicit justification.

## Local purpose
Provide a CI-executable validation surface for every contract, module, and governance rule.
Tests must be deterministic: same inputs → same results, with no network or filesystem side effects.
Use fixtures in `tests/fixtures/` for all input data. Do not use live external data in tests.

## Constraints
- **No test removal**: Removing or disabling a test requires explicit PLAN justification. Broken tests must be fixed, not deleted.
- **No network access in tests**: Validated by `tests/test_no_network_schema_loading.py`. Schemas load from local files only.
- **Fixture-first**: New tests must use deterministic fixtures. Do not generate random data in tests.
- **One concern per test file**: Do not merge unrelated test concerns into a single file.
- **No unrelated refactors**: Do not rename, restructure, or reformat test files outside the declared scope of a prompt.

## Required validation surface
Before any `BUILD` or `VALIDATE` prompt is marked complete:
1. Run the relevant test file(s) for the changed module or contract.
2. Run `pytest tests/test_contracts.py` if any contract was modified.
3. Run `pytest tests/test_module_architecture.py` if module structure was changed.
4. Run `pytest tests/test_core_loop_pre_pr_gate.py tests/test_check_agent_pr_ready.py tests/test_agent_core_loop_requires_clp.py` for any repo-mutating work — CLP-02 requires `core_loop_pre_pr_gate_result` evidence and a passing `agent_pr_ready_result` guard before PR-ready handoff.
5. All tests must pass before the step is marked done.

## Files that must not be changed casually
| File | Reason |
| --- | --- |
| `tests/test_no_network_schema_loading.py` | Enforces offline-first schema loading — changing this weakens a critical guardrail |
| `tests/test_contract_enforcement.py` | Primary contract conformance test — removing cases hides regressions |
| `tests/test_gap_detection.py` | Comprehensive gap detection coverage — 35KB of deterministic cases |
| `tests/test_observability.py` | Observability coverage — 35KB of instrumentation validation |
| `tests/fixtures/` | Canonical test inputs — changes require review against all dependent tests |

## Nearby files (read before editing)
- `tests/fixtures/` — deterministic test input data
- `contracts/examples/` — golden-path contract payloads (used as test inputs)
- `scripts/run_contract_enforcement.py` — contract enforcement script (complements tests)
- `pytest.ini` or `setup.cfg` — test configuration
