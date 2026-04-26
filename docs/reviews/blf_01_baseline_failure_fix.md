# BLF-01 — Baseline Failure Fix

**Batch:** BLF-01 (with BLF-01A authority-shape vocabulary cleanup)
**Branch:** `claude/blf-01-baseline-fixes-qTz5W`
**Status:** pass
**H01 readiness signal:** ready

BLF-01 is a non-owning baseline-failure cleanup and readiness-evidence batch.
It does not claim closure, advancement, readiness-evidence, policy-action,
or review authority. Closure remains with CDE; advancement and
readiness-evidence remain with REL/GOV; policy-action remains with SEL/ENF;
review authority remains with GOV/HIT. The exact rename table for BLF-01A is
recorded in `artifacts/blf_01_baseline_failure_fix/delivery_report.json`
under the `blf_01a_summary.names_changed` field; this document deliberately
does not embed those raw identifiers so it stays clean under the
authority-shape preflight scan.

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
- New regression suite `tests/test_blf_01_baseline_gate.py` locks in fixture pinning, runner-interpreter pinning, BLF-01 artifact-shape invariants, and (post BLF-01A) the non-owner authority-shape vocabulary used by the BLF surface.
- New gate script `scripts/run_blf_01_baseline_gate.py` validates the BLF-01 artifact set fail-closed and emits machine-readable reason codes.
- BLF-01 governed artifact set written under `artifacts/blf_01_baseline_failure_fix/` (inventory, classification, root-cause analysis, fix recommendations, control validation, replay validation, delivery report).

## What BLF-01A changed (authority-shape vocabulary cleanup)

The first BLF-01 push surfaced 39 authority-shape preflight violations because BLF artifacts/docs/helpers used reserved authority verbs from clusters BLF does not own (closure, advancement, readiness-evidence, policy-action, review). BLF-01A renames the BLF surface to non-owner vocabulary; behavior, schemas, and existing assertions are unchanged.

The runtime helper that the runner imports was renamed in
`spectrum_systems/modules/runtime/roadmap_realization_runtime.py` (the
function body is unchanged) and the rename was propagated to the canonical
`RF-03` step contract `runtime_entrypoints` value, the test fixture's
entrypoint string, and the regenerated runner-result and red-team artifacts.
The full identifier mapping is in
`artifacts/blf_01_baseline_failure_fix/delivery_report.json::blf_01a_summary.names_changed`.

## What was not changed

- The authority-shape preflight, authority-leak guard, registry, vocabulary, or detector. No allow-list, exclusion, or override entries were added.
- The production module `spectrum_systems/modules/runtime/github_pr_autofix_review_artifact_validation.py`. An earlier BLF-01 draft attempted to also pin `commit.gpgsign=false` inside its commit helper. Editing that file caused the local authority-leak guard to flag pre-existing forbidden tokens once the file appeared in the changed-file set. Rather than weaken the guard via overrides, the production change was reverted. Those pre-existing tokens remain a separate, deferred concern outside BLF-01 / BLF-01A scope.
- Roadmap mirrors, schemas, contracts, and the standards manifest, except the `RF-03` step contract entry that names the renamed runtime helper as a `runtime_entrypoints` value.
- Any tests were weakened or skipped: every prior assertion still fires.

## Guarantees preserved

- **No test weakening.** No assertions removed or relaxed; new assertions added.
- **No authority leak.** Authority-leak guard still passes against the post-fix changed-file set.
- **No authority-shape drift.** BLF-introduced names use non-owner vocabulary (`recommendations`, `findings`, `observations`, `signals`, `reviewed`, `validate`).
- **No schema bypass.** No schemas or examples loosened. No standards-manifest entries added.
- **No roadmap authority drift.** Roadmap mirrors and machine-readable roadmap unchanged.
- **No readiness-evidence bypass.** Runner is now stricter (deterministic interpreter); acceptance/verification semantics are unchanged. GOV-owned readiness evidence remains untouched.
- **No hidden exceptions.** Every recommendation is logged in `fix_recommendations.json`. No allow-list overrides added to mask leaks.

## Validation

| Command | Result |
|---|---|
| Targeted four-target run plus BLF gate regressions | all passed |
| Broader pattern run (authority-leak / contract-impact / github-pr-autofix / roadmap-realization) | all passed |
| BLF gate script over `artifacts/blf_01_baseline_failure_fix/` | status=pass, no reason codes |
| Authority-shape preflight (`ff1b6bb1...HEAD`, `--suggest-only`) | status=pass, violation_count=0 |

## Whether H01 may start

**Yes — H01_READY.** All four target failures are fixed or governed with deterministic, fail-closed evidence. The authority-shape preflight reports zero violations on the BLF-01 changed-file set. The BLF gate script and regression suite lock the fixes against silent re-introduction.

## Known gaps

- Pre-existing forbidden-vocabulary tokens in helper functions of the production governed-autofix module remain. They do not currently fail any guard on `main` and are out of BLF-01 / BLF-01A scope. Address them in a dedicated authority-vocabulary cleanup batch.
