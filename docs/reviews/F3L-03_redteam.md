# F3L-03 Red-Team — Persist PRL Artifacts Deterministically

Scope: red-team review of the F3L-03 slice. F3L-03 changes
`scripts/run_pre_pr_reliability_gate.py` to persist its emitted
artifacts to stable filesystem paths under a configurable
`--output-dir` (default `outputs/prl/`). The persisted artifacts give
APU and replay consumers a file-based evidence surface that does not
depend on parsing the legacy stdout NDJSON stream.

Authority boundary preserved: PRL remains the owner of failure
classification, repair-candidate, and eval-candidate evidence. The
file-writing behavior is a persistence detail; it does not introduce a
new gate, change CLP gate-status authority, or shift APU's
observation-only role. Canonical authority remains with the systems
declared in `docs/architecture/system_registry.md`.

## Authority-safe vocabulary

This document avoids reserved owner-authority verbs and their negated
forms. PRL emits failure, repair-candidate, and eval-candidate
evidence. APU emits PR-update readiness observations. CLP emits a
pre-PR gate status. None of these systems claim admission,
execution-closure, eval, policy, continuation, or final-gate signal
authority on behalf of canonical owners.

## Threat scenarios

### 1. PRL artifacts only available as stdout NDJSON

Disposition: **closed by F3L-03**.
Mechanism: `run_gate` accepts an `output_dir` argument. When supplied
(default `outputs/prl/`), each emitted artifact is also written to a
stable file path under a canonical subdirectory layout:

| artifact_type | subdirectory |
| --- | --- |
| `pr_failure_capture_record` | `captures/` |
| `pre_pr_failure_packet` | `failure_packets/` |
| `prl_repair_candidate` | `repair_candidates/` |
| `eval_case_candidate` | `eval_candidates/` |
| `prl_eval_case` | `eval_cases/` |
| `prl_eval_generation_record` | `eval_generation_records/` |

The final `prl_gate_result` is written to `prl_gate_result.json`. Test:
`tests/prl/test_pre_pr_gate_persistence.py::test_run_gate_writes_gate_result_file`.

### 2. Gate-result refs lose deterministic file paths

Disposition: **closed**.
Mechanism: `failure_packet_refs`, `repair_candidate_refs`, and
`eval_candidate_refs` in `prl_gate_result` now include the relative
file path for every persisted artifact alongside the legacy
`<artifact_type>:<id>` strings, so APU and replay consumers can resolve
the artifact directly from disk. Test:
`tests/prl/test_pre_pr_gate_persistence.py::test_run_gate_writes_failure_packets_to_stable_paths`.

### 3. Second run produces structural diff vs first

Disposition: **closed**.
Mechanism: artifact ids are computed via `deterministic_id` from the
artifact payload (already deterministic across runs given the same
classification, message, capture refs, and run scope). The persistence
layer writes the artifact body via `json.dumps(..., indent=2,
sort_keys=True)`, so the on-disk byte order is stable. Volatile fields
(timestamps, run_id, trace_id, derived ids) are excluded from the
structural normalization used by replay tests. Test:
`tests/prl/test_pre_pr_gate_persistence.py::test_two_runs_produce_no_structural_diff`.

### 4. Replay impossible from artifacts alone

Disposition: **closed**.
Mechanism: every reference in `prl_gate_result.json` resolves to a
file on disk under the canonical subdir. The test reads the gate
result back from disk and asserts it matches the in-memory object,
then walks every file-path ref and validates the artifact body. Test:
`tests/prl/test_pre_pr_gate_persistence.py::test_replay_from_artifacts_alone`.

### 5. APU still depends on stdout NDJSON

Disposition: **closed**.
Mechanism: `scripts/check_agent_pr_update_ready.py` already loads PRL
evidence from `outputs/prl/prl_gate_result.json` via
`load_prl_result`. With F3L-03's file-based persistence, the auto-run
no longer needs to parse the runner's stdout for the gate-result; the
runner writes it directly. The auto-invoker keeps a stdout fallback
for legacy callers but the canonical path is file-based. Test:
`tests/test_prl_auto_invoker.py::test_auto_run_accepts_runner_written_file_when_stdout_silent`.

### 6. File persistence introduces new gate authority

Disposition: **closed by design**.
Mechanism: the persistence layer only writes artifacts; it does not
classify, decide, or emit a gate signal. CLP gate-status authority,
PRL classification authority, and APU observation-only role are
unchanged. The runner exit codes are unchanged.

### 7. `--output-dir` empty value silently disables persistence

Disposition: **closed (documented)**.
Mechanism: `--output-dir ""` opts out of file persistence and emits
the legacy stdout-only stream. This keeps the legacy CI invocation
working, while the default path enables the file-based evidence
surface APU now consumes. Test:
`tests/prl/test_pre_pr_gate_persistence.py::test_output_dir_none_disables_persistence`.

### 8. Auto-invoker creates artifacts that contradict PRL's own writes

Disposition: **closed**.
Mechanism: when PRL writes the gate-result file via F3L-03, the
auto-invoker's `_extract_gate_result_from_stdout` still observes the
final NDJSON line and writes the same payload (idempotent overwrite
with sorted keys). No conflicting artifact is produced. The fallback
"runner_written_file" branch covers the case where PRL writes the file
but stdout is silent (e.g. piped). Test:
`tests/test_prl_auto_invoker.py::test_auto_run_accepts_runner_written_file_when_stdout_silent`.

## Closure

All threat scenarios listed in the F3L-03 task brief are addressed by
the changes above. PRL artifact persistence is deterministic,
schema-validated, and consumable by APU and replay observers without
parsing the legacy stdout NDJSON stream.
