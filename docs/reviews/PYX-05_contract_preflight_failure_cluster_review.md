# PYX-05 — contract_preflight failure cluster review

## Failure cluster summary
Targeted failures are concentrated in:
- `tests/test_contract_preflight.py`
- `tests/test_pqx_preflight_wrapper_compatibility.py`

The failing cases are all synthetic no-op / inspection / controlled-wrapper scenarios that expected non-PR semantics (`code == 0`), but observed `code == 2` with `strategy_gate_decision=BLOCK` and classification around `no_tests_discovered` / `pytest_selection_missing`.

## Why these tests used to pass
These tests monkeypatch `_parse_args` and often omit explicit `event_name`. Historically they passed when ambient environment did not signal `pull_request`, so preflight ran non-PR semantics and did not enforce PR-only pytest evidence strictness.

## Why they now fail in CI
`run_contract_preflight.main()` resolves event context via `normalize_preflight_ref_context(event_name=args.event_name, env=os.environ, ...)`. If tests do not set `event_name`, CI-provided environment can imply PR context. Under PR context, stricter evidence and selection-integrity invariants correctly fail closed, producing the observed BLOCK/no-tests-discovered cluster.

## Boundary decisions
### Must remain BLOCK (no change)
Real PR/governed trust paths must continue to block when:
- pytest execution evidence is missing,
- selection-integrity evidence is missing/blocked,
- degraded PR resolution is detected,
- WARN-like PR pass equivalents are attempted.

### Should remain ALLOW/WARN/no-op in this cluster
Synthetic non-PR inspection/no-op/unit-test scenarios should remain deterministic and non-PR-scoped when they are explicitly testing analysis behavior rather than PR trust-gate behavior.

## Repair strategy
- Do **not** relax production enforcement.
- Update the listed tests to provide explicit non-PR `event_name` (e.g., `push`) in mocked args, so semantics are deterministic regardless of CI ambient env.
- Keep PR strictness tests separate and unchanged.
