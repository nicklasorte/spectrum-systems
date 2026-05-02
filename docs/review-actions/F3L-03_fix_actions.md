# F3L-03 Fix Actions — Persist PRL Artifacts Deterministically

Each entry below records a must_fix finding from the F3L-03 red-team
review, the file changed to address it, the test that proves the fix,
the validation command run, and the disposition.

| Finding ID | File changed | Test added/updated | Command run | Disposition |
| --- | --- | --- | --- | --- |
| F3L-03-RT-01 (PRL artifacts only available as stdout NDJSON) | `scripts/run_pre_pr_reliability_gate.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_run_gate_writes_gate_result_file` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |
| F3L-03-RT-02 (Gate-result refs lose deterministic file paths) | `scripts/run_pre_pr_reliability_gate.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_run_gate_writes_failure_packets_to_stable_paths`, `tests/prl/test_pre_pr_gate_persistence.py::test_run_gate_persists_repair_and_eval_candidates` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |
| F3L-03-RT-03 (Second run produces structural diff vs first) | `scripts/run_pre_pr_reliability_gate.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_two_runs_produce_no_structural_diff` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |
| F3L-03-RT-04 (Replay impossible from artifacts alone) | `scripts/run_pre_pr_reliability_gate.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_replay_from_artifacts_alone` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |
| F3L-03-RT-05 (APU still depends on stdout NDJSON) | `scripts/check_agent_pr_update_ready.py`, `spectrum_systems/modules/runtime/prl_auto_invoker.py` | `tests/test_prl_auto_invoker.py::test_auto_run_accepts_runner_written_file_when_stdout_silent` | `python -m pytest tests/test_prl_auto_invoker.py -q` | Closed |
| F3L-03-RT-06 (File persistence introduces new gate authority) | (no change — persistence is observation-only) | n/a (verified by absence of new gate paths) | `python -m pytest tests/prl/ tests/test_prl_auto_invoker.py tests/test_check_agent_pr_update_ready.py -q` | Closed (no regression) |
| F3L-03-RT-07 (`--output-dir` empty value silently disables persistence) | `scripts/run_pre_pr_reliability_gate.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_output_dir_none_disables_persistence` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed (documented) |
| F3L-03-RT-08 (Auto-invoker creates artifacts that contradict PRL's own writes) | `spectrum_systems/modules/runtime/prl_auto_invoker.py` | `tests/test_prl_auto_invoker.py::test_auto_run_accepts_runner_written_file_when_stdout_silent` | `python -m pytest tests/test_prl_auto_invoker.py -q` | Closed |

## Test summary

```
python -m pytest tests/prl/ tests/test_prl_auto_invoker.py tests/test_check_agent_pr_update_ready.py -q
```

Result: 153 passed (7 new F3L-03 persistence cases + existing
PRL/APU/auto-invoker suites).

## Authority boundary check

PRL retains classification, repair-candidate, and eval-candidate
authority. The persistence layer only writes artifacts to stable
filesystem paths; it does not classify, decide, or emit a gate signal.
CLP gate-status authority and APU observation-only role are unchanged.
Canonical authority remains with the systems declared in
`docs/architecture/system_registry.md`. F3L-03 does not redefine PRL,
CLP, AEX, PQX, EVL, TPA, CDE, SEL, LIN, REP, or GOV authority.

## Unresolved must_fix findings

None. All red-team must_fix findings closed by F3L-03 with passing
tests.
