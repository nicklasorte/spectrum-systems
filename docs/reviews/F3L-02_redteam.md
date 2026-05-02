# F3L-02 Red-Team — Auto-Invoke PRL When CLP Blocks

Scope: red-team review of the F3L-02 slice. F3L-02 closes the manual
seam between CLP gate-status detection and PRL failure-normalization by
auto-invoking `scripts/run_pre_pr_reliability_gate.py` from the APU
PR-update readiness guard whenever CLP reports the blocking gate status
on a repo-mutating slice and PRL evidence is missing or stale.

Authority boundary preserved: APU remains observation-only. PRL retains
all classification, repair-candidate, and eval-candidate authority. CLP
retains gate-status authority. The auto-invoker is a non-owning support
shim that only invokes PRL and persists its gate-result artifact at the
canonical path so APU has artifact-backed evidence to observe.
Canonical authority remains with the systems declared in
`docs/architecture/system_registry.md`.

## Authority-safe vocabulary

This document avoids reserved owner-authority verbs and their negated
forms. APU emits PR-update readiness observations. The auto-invoker
emits an invocation-record observation only. PRL emits failure,
repair-candidate, and eval-candidate evidence. CLP emits a pre-PR gate
status. None of these systems claim admission, execution-closure, eval,
policy, continuation, or final-gate signal authority on behalf of
canonical owners.

## Threat scenarios

### 1. Manual operator forgets to run PRL after CLP block

Disposition: **closed by F3L-02**.
Mechanism: `scripts/check_agent_pr_update_ready.py` now calls
`auto_run_prl_if_clp_blocked` before evaluating readiness. When CLP
gate status is blocking and `repo_mutating=True`, PRL is invoked as a
subprocess and its `prl_gate_result` is persisted at
`outputs/prl/prl_gate_result.json`. Test:
`tests/test_prl_auto_invoker.py::test_auto_run_writes_gate_result_from_stdout`.

### 2. Auto-invoker silently swallows PRL failures

Disposition: **closed**.
Mechanism: when PRL exits non-zero or emits no `prl_gate_result` line
on stdout (and no file is found at the canonical path), the helper
returns `status="error"` with stable reason codes. APU's
`evaluate_pr_update_ready` surfaces `prl_auto_invocation_failed` plus
each downstream reason code on the readiness artifact and adds a PRL
follow-up. Tests:
`tests/test_prl_auto_invoker.py::test_auto_run_returns_error_when_no_gate_result`
and `tests/test_check_agent_pr_update_ready.py::test_prl_auto_invocation_error_surfaces_reason_codes`.

### 3. Auto-invoker overwrites a fresh PRL artifact

Disposition: **closed**.
Mechanism: `should_auto_run_prl` short-circuits with reason
`prl_artifact_already_present` when the PRL artifact exists and its
mtime is no older than the CLP artifact's. Stale PRL artifacts (older
than the CLP artifact they should explain) are treated as missing so
PRL re-runs. Tests:
`test_should_skip_when_prl_artifact_present_and_fresh`,
`test_should_run_when_prl_artifact_stale`.

### 4. Auto-run claims PRL or APU authority

Disposition: **closed**.
Mechanism: the invocation record carries
`authority_scope="observation_only"`. The helper module docstring,
schema (`prl_auto_invocation`), and policy notes all spell out that PRL
retains repair/eval/classification authority and APU remains
observation-only. The forbidden-vocabulary regression test
`test_prl_artifact_negated_authority_phrases_absent` continues to pass.

### 5. Auto-run masks CLP block

Disposition: **closed by design**.
Mechanism: the helper never modifies CLP, never reclassifies the gate
status, and never advances the readiness signal on its own. CLP's
gate_status remains the input to `evaluate_pr_update_ready`. APU still
emits `not_ready` for CLP block status; the auto-invoker only ensures
PRL evidence is present so the reason codes are precise.

### 6. CLP not blocking → unnecessary PRL invocation

Disposition: **closed**.
Mechanism: `should_auto_run_prl` returns `False` with reason
`clp_not_blocking` when CLP gate status is not the blocking value, and
`repo_mutating_not_true` when the slice does not mutate the repo. Test:
`test_should_skip_when_clp_not_blocking`,
`test_should_skip_when_repo_mutating_false`.

### 7. Subprocess launch failure / missing runner

Disposition: **closed**.
Mechanism: missing runner returns `status="error"` with reason
`prl_runner_not_found`. Subprocess exceptions return
`prl_subprocess_launch_failed` with the exception type appended to
`reason_codes`. Tests:
`test_auto_run_writes_gate_result_from_stdout` (asserts the
`prl_runner_not_found` path) and
`test_auto_run_subprocess_launch_failure_returns_error`.

### 8. Replay drift — auto-run produces non-deterministic artifacts

Disposition: **partially closed; F3L-03 owns determinism**.
Mechanism: F3L-02 only persists the gate-result file from PRL's stdout
when PRL itself does not write one. F3L-03 makes PRL write the file
deterministically with `--output-dir`, removing the auto-invoker's
fallback path for ordinary runs. The remaining auto-invoker fallback
exists solely to keep the seam closed when PRL is run in legacy
stdout-only mode.

## Closure

All threat scenarios listed in the F3L-02 task brief are addressed by
the changes above. The auto-invoker is observation-only, fail-closed,
and non-authority-claiming.
