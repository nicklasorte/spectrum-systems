# BLF-01 — Baseline Failure Fix

**Batch:** BLF-01
**Branch:** `claude/blf-01-baseline-fixes-qTz5W`
**Status:** pass
**H01 readiness:** ready

## What failed

Four pre-existing failures were reported on the RFX-04 PR (#1215) baseline:

| Test | Behavior |
|---|---|
| `test_authority_leak_guard_local::test_authority_leak_guard_passes_on_local_changes` | Reported failing on the RFX-04 working tree; not reproducible on the post-merge commit. |
| `test_contract_impact_analysis` (5 cases) | All cases failed with `git commit ... returned non-zero exit status 128` because the temp-repo fixture inherited the host's `commit.gpgsign=true` global config. |
| `test_github_pr_autofix_review_artifact_validation` (8 cases) | Same fixture coupling: host signing required; temp repo could not satisfy it. |
| `test_roadmap_realization_runner::test_verified_requires_stricter_behavioral_coverage_than_runtime_realized` | Runner's behavioral-pytest subprocess resolved `pytest` via PATH and used a separate tool venv lacking project dependencies (e.g. `jsonschema`); the proof failed for environmental, not behavioral, reasons. |

## What was fixed

- `tests/test_contract_impact_analysis.py::_init_repo` and `tests/test_github_pr_autofix_review_artifact_validation.py::_init_git_repo` now also pin `commit.gpgsign=false` and `tag.gpgsign=false` locally on every temp repo so host signing config cannot leak in.
- `scripts/roadmap_realization_runner.py::_run_behavioral_tests` now normalizes `pytest tests/...` and `python -m pytest tests/...` invocations to `[sys.executable, -m, pytest, ...]`, sealing the behavioral subprocess to the runner's own interpreter.
- New regression test suite `tests/test_blf_01_baseline_gate.py` (11 cases) locks in fixture-pinning, runner-pinning, and BLF-01 artifact-shape invariants.
- New gate script `scripts/run_blf_01_baseline_gate.py` validates the BLF-01 artifact set fail-closed and emits machine-readable reason codes.
- BLF-01 governed artifact set written under `artifacts/blf_01_baseline_failure_fix/` (inventory, classification, root-cause analysis, fix decisions, control validation, replay validation, delivery report).

## What was not changed

- The authority-leak guard, registry, and scripts: failure was non-reproducible, so no remediation is in scope.
- The production module `spectrum_systems/modules/runtime/github_pr_autofix_review_artifact_validation.py`: an earlier draft attempted to also pin `commit.gpgsign=false` inside `_git_commit_changes`. Editing that file caused the local authority-leak guard to flag pre-existing forbidden tokens (`allow`/`block`/`decision`/`promotion_ready` in helper functions) once the file appeared in the changed-file set. Rather than weaken the guard via overrides, the production change was reverted; the test fixture pin alone is sufficient because production commits run inside the fixture-sealed temp repo where local config beats global. The pre-existing forbidden-vocabulary tokens in that module remain a separate, deferred concern outside BLF-01 scope.
- Roadmap mirrors, schemas, contracts, and the standards manifest: no edits required to land BLF-01.
- Any tests were weakened or skipped: every prior assertion still fires.

## Guarantees preserved

- **No test weakening.** No assertions removed or relaxed; new assertions added.
- **No authority leak.** Authority-leak guard still passes against the post-fix changed-file set.
- **No schema bypass.** No schemas or examples loosened. No standards-manifest entries added.
- **No roadmap authority drift.** Roadmap mirrors and machine-readable roadmap unchanged.
- **No promotion / certification bypass.** Runner is now stricter (deterministic interpreter) and acceptance/verification semantics are unchanged.
- **No hidden exceptions.** Every fix is logged in `fix_decisions.json`. No allowed-values overrides added to mask leaks.

## Validation

| Command | Result |
|---|---|
| `python3 -m pytest tests/test_authority_leak_guard_local.py tests/test_contract_impact_analysis.py tests/test_github_pr_autofix_review_artifact_validation.py tests/test_roadmap_realization_runner.py -q` | 39 passed |
| `python3 -m pytest tests/ -q -k "authority_leak or contract_impact or github_pr_autofix or roadmap_realization"` | 90 passed |
| `python3 -m pytest tests/ -q -k blf_01` | All BLF gate regression cases pass |
| `python3 -m pytest tests/ -q --ignore=tests/hop --ignore=tests/replay --ignore=tests/integration --ignore=tests/e2e -x` | 8808 passed, 1 skipped, 36 warnings (267.50s) |
| `python3 scripts/run_blf_01_baseline_gate.py --artifact-dir artifacts/blf_01_baseline_failure_fix` | status=pass, no reason codes |

## Whether H01 may start

**Yes — H01_READY.** All four target failures are fixed or governed with deterministic, fail-closed evidence. The broad unit tier passes with no BLF-introduced regressions. The BLF gate script and regression suite lock the fixes against silent re-introduction.

## Known gaps

- Pre-existing forbidden-vocabulary tokens in the production governed-autofix module helper functions remain. They do not currently fail any guard on `main` and are out of BLF-01 scope. Address them in a dedicated authority-vocabulary cleanup batch.
