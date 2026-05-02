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
| F3L-03-RT-09 (APU still resolves PRL evidence via NDJSON parsing instead of a file-backed index) | `scripts/run_pre_pr_reliability_gate.py`, `contracts/schemas/prl_artifact_index.schema.json`, `contracts/examples/prl_artifact_index.example.json`, `contracts/standards-manifest.json`, `spectrum_systems/modules/runtime/agent_pr_update_policy.py`, `scripts/check_agent_pr_update_ready.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_run_gate_writes_artifact_index`, `::test_apu_consumes_file_backed_refs_from_index` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |
| F3L-03-RT-10 (Missing index treated as ready when CLP blocks repo-mutating work) | `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_missing_index_yields_not_ready_when_clp_blocks` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |
| F3L-03-RT-11 (Stale PRL index reused after CLP changed) | `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_stale_index_gate_ref_mismatch_surfaces_reason_code` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |
| F3L-03-RT-12 (Partial index treated as ready) | `scripts/run_pre_pr_reliability_gate.py`, `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_partial_index_yields_reason_codes` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |
| F3L-03-RT-13 (APU consumes PRL prose instead of artifact refs) | `scripts/run_pre_pr_reliability_gate.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_index_lists_only_file_backed_refs`, `::test_apu_consumes_file_backed_refs_from_index` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |
| F3L-03-RT-14 (PRL persistence bypasses current repair/eval ownership) | `contracts/schemas/prl_artifact_index.schema.json` | n/a (schema enforces `authority_scope: observation_only`; no new repair / eval generation surfaces) | `python -m pytest tests/prl/ -q` | Closed (no regression) |
| F3L-03-RT-15 (Authority language regression in index artifact) | `contracts/schemas/prl_artifact_index.schema.json`, `spectrum_systems/modules/runtime/agent_pr_update_policy.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_index_authority_scope_drift_blocks_readiness` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |
| F3L-03-RT-16 (Generated index unstable after second run) | `scripts/run_pre_pr_reliability_gate.py` | `tests/prl/test_pre_pr_gate_persistence.py::test_index_structure_stable_across_runs`, `::test_index_deterministic_when_inputs_pinned`, `::test_index_disk_round_trip_preserves_evidence_hash` | `python -m pytest tests/prl/test_pre_pr_gate_persistence.py -q` | Closed |

## Test summary

```
python -m pytest tests/prl/ tests/test_prl_auto_invoker.py tests/test_check_agent_pr_update_ready.py -q
```

Result: 214 passed (18 F3L-03 persistence cases — 7 original + 11 new
index-related cases — plus existing PRL/APU/auto-invoker suites).

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
