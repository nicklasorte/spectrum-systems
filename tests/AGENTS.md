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

## AEX Admission Rule

All repo-mutating agent work must begin with an AEX-style admission step before implementation.

Before editing any files, the agent must identify:

- request type and intended outcome
- exact changed surfaces (files, workflows, schemas, tests, docs)
- authority-shape risks across canonical-owner boundaries (per `docs/architecture/system_registry.md`)
- required tests and eval coverage
- required schema or artifact updates
- required governance mappings, where they exist (e.g. test-gating, selection, and ownership mappings declared in `docs/architecture/system_registry.md` or `docs/governance/`)
- required replay and observability updates
- whether the scope is too large and must be split

If the work touches any governed surface, including:

- `.github/workflows/`
- `scripts/`
- `contracts/`
- `spectrum_systems/`
- `tests/`
- `docs/governance/`
- system registry or architecture artifacts

then the agent must either:

1. Update all corresponding mappings, tests, schemas, and governance artifacts in the same change
1. OR stop and report the missing mapping before proceeding

### Authority Boundary

AEX is an admission boundary only.

It may produce:

- admission evidence
- policy observations
- normalized execution requests
- downstream input signals
- trace / provenance / lineage

It must NOT claim or implement:

- enforcement authority
- certification authority
- promotion authority
- final control decisions

All such authority remains with the canonical owner declared in `docs/architecture/system_registry.md`. AEX emits admission evidence and downstream support inputs only; it does not redefine any 3-letter system's ownership.

### Fail-Closed Principle

If required signals, mappings, or coverage are missing, the agent must fail closed:

- do not proceed with implementation
- do not create partial or unmapped changes
- do not assume downstream systems will "handle it"

Instead:

- report the gap
- propose the minimal required fix
- or split the work into smaller, admissible slices

### Intent

This rule ensures:

- no orphaned workflows, scripts, or schemas
- no missing test coverage for governed surfaces
- no authority-shape violations
- no hidden logic outside governed artifacts
- no CI drift caused by agent-generated changes

All changes must be admissible, traceable, testable, and governed before execution.

## Required validation surface
Before any `BUILD` or `VALIDATE` prompt is marked complete:
1. Run the relevant test file(s) for the changed module or contract.
2. Run `pytest tests/test_contracts.py` if any contract was modified.
3. Run `pytest tests/test_module_architecture.py` if module structure was changed.
4. All tests must pass before the step is marked done.

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
