# F3L-02 Fix Actions — Auto-Invoke PRL When CLP Blocks

Each entry below records a must_fix finding from the F3L-02 red-team
review, the file changed to address it, the test that proves the fix,
the validation command run, and the disposition.

| Finding ID | File changed | Test added/updated | Command run | Disposition |
| --- | --- | --- | --- | --- |
| F3L-02-RT-01 (Manual operator forgets to run PRL after CLP block) | `spectrum_systems/modules/runtime/prl_auto_invoker.py`, `scripts/check_agent_pr_update_ready.py` | `tests/test_prl_auto_invoker.py::test_auto_run_writes_gate_result_from_stdout` | `python -m pytest tests/test_prl_auto_invoker.py -q` | Closed |
| F3L-02-RT-02 (Auto-invoker silently swallows PRL failures) | `spectrum_systems/modules/runtime/prl_auto_invoker.py`, `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `tests/test_prl_auto_invoker.py::test_auto_run_returns_error_when_no_gate_result`, `tests/test_check_agent_pr_update_ready.py::test_prl_auto_invocation_error_surfaces_reason_codes` | `python -m pytest tests/test_prl_auto_invoker.py tests/test_check_agent_pr_update_ready.py -q` | Closed |
| F3L-02-RT-03 (Auto-invoker overwrites a fresh PRL artifact) | `spectrum_systems/modules/runtime/prl_auto_invoker.py` | `tests/test_prl_auto_invoker.py::test_should_skip_when_prl_artifact_present_and_fresh`, `tests/test_prl_auto_invoker.py::test_should_run_when_prl_artifact_stale` | `python -m pytest tests/test_prl_auto_invoker.py -q` | Closed |
| F3L-02-RT-04 (Auto-run claims PRL or APU authority) | `spectrum_systems/modules/runtime/prl_auto_invoker.py`, `contracts/schemas/agent_pr_update_ready_result.schema.json`, `contracts/examples/agent_pr_update_ready_result.example.json` | `tests/test_check_agent_pr_update_ready.py::test_prl_auto_invocation_record_serialized_into_artifact`, existing `test_prl_artifact_negated_authority_phrases_absent` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Closed |
| F3L-02-RT-05 (Auto-run masks CLP block) | (no change — CLP block path preserved in `evaluate_pr_update_ready`) | existing `test_clp_block_with_no_prl_evidence_yields_not_ready`, new `test_prl_auto_invocation_skipped_does_not_surface_reasons` | `python -m pytest tests/test_check_agent_pr_update_ready.py -q` | Closed (no regression) |
| F3L-02-RT-06 (CLP not blocking → unnecessary PRL invocation) | `spectrum_systems/modules/runtime/prl_auto_invoker.py` | `tests/test_prl_auto_invoker.py::test_should_skip_when_clp_not_blocking`, `tests/test_prl_auto_invoker.py::test_should_skip_when_repo_mutating_false` | `python -m pytest tests/test_prl_auto_invoker.py -q` | Closed |
| F3L-02-RT-07 (Subprocess launch failure / missing runner) | `spectrum_systems/modules/runtime/prl_auto_invoker.py` | `tests/test_prl_auto_invoker.py::test_auto_run_subprocess_launch_failure_returns_error`, partial coverage in `test_auto_run_writes_gate_result_from_stdout` | `python -m pytest tests/test_prl_auto_invoker.py -q` | Closed |
| F3L-02-RT-08 (Replay drift — auto-run produces non-deterministic artifacts) | (handed off to F3L-03; auto-invoker only persists when PRL writes nothing) | `tests/prl/test_pre_pr_gate_persistence.py::test_two_runs_produce_no_structural_diff` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed via F3L-03 |

## Test summary

```
python -m pytest tests/test_prl_auto_invoker.py tests/test_check_agent_pr_update_ready.py -q
```

Result: 56 passed (14 new F3L-02 auto-invoker cases + 39 APU cases + 3
new F3L-02 wiring cases on the APU evaluator).

## Authority boundary check

APU remains observation-only. The auto-invoker is a non-owning support
shim that only invokes PRL and persists its gate-result artifact at the
canonical path. PRL retains classification, repair-candidate, and
eval-candidate authority. Canonical authority remains with the systems
declared in `docs/architecture/system_registry.md`. F3L-02 does not
redefine PRL, CLP, AEX, PQX, EVL, TPA, CDE, SEL, LIN, REP, or GOV
authority.

## Unresolved must_fix findings

None. All red-team must_fix findings closed by F3L-02 with passing
tests.
