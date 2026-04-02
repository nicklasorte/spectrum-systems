# CON-037 — Default PQX Execution Policy for Governed Work

- **Status:** Active
- **Effective date:** 2026-04-02
- **Enforcement seam:** `scripts/run_contract_preflight.py`
- **Classifier module:** `spectrum_systems/modules/runtime/pqx_execution_policy.py`

## Policy statement

Governed merge-intended execution in this repository is **PQX-required by default**.

Direct non-PQX execution is non-authoritative by default and must not be interpreted as governed merge-ready success.

## Governed surfaces (deterministic path classes)

A changed-path set is `governed_pqx_required` when any path matches one or more of the classes below:

1. `spectrum_systems/` implementation surfaces.
2. `contracts/` schemas, examples, and standards registry surfaces.
3. Runtime/control/orchestration/promotion/certification/replay/PQX seams under:
   - `spectrum_systems/modules/runtime/`
   - `spectrum_systems/orchestration/`
4. Policy-governed scripts and deterministic test seams tied to those surfaces:
   - `scripts/run_contract_preflight.py`
   - `scripts/pqx_runner.py`
   - `scripts/run_contract_enforcement.py`
   - `tests/test_contract_preflight.py`
   - `tests/test_pqx_slice_runner.py`
   - `tests/test_done_certification.py`
   - `tests/test_sequence_transition_policy.py`
   - `tests/test_contracts.py`
   - `tests/test_contract_enforcement.py`

Any changed-path set with no matching governed path class is `exploration_only_or_non_governed`.

## Allowed direct-run exceptions (non-authoritative only)

Direct execution may be used for narrow non-authoritative contexts:

- local exploration,
- debugging,
- draft planning,
- non-governed notes.

These exceptions:

- do not establish governed merge readiness,
- do not count as promotion/certification authority,
- are explicitly marked `non_authoritative_direct_run` by policy evaluation.

## Fail-closed rules

1. If governed paths are present and PQX execution context is missing or non-PQX, policy decision is `block`.
2. If changed-path input is malformed or ambiguous, policy decision is `block`.
3. Only governed + explicit PQX context can produce `authoritative_governed_pqx` status.
