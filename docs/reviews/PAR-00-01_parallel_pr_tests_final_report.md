# PAR-00-01 Final Report: Canonical Selector + Parallel PR Shards + 3LS Precheck Parity

**Batch**: PAR-00-01
**Produced**: 2026-04-29
**Status**: Implementation complete

---

## 1. Original Bottleneck

PR tests ran in a single serial job (`pytest:` in `pr-pytest.yml`), driven exclusively by
`scripts/run_contract_preflight.py`. Problems identified:

- Serial execution could take 15+ minutes on governed-surface changes.
- Test-selection logic was embedded inline in `run_contract_preflight.py` with no canonical
  module boundary — CI and 3LS pre-checks could diverge.
- `pytest_selection_missing` failures had already occurred (no governed selector).
- No parallel shard evidence meant a single slow test blocked the whole gate.
- Missing evidence (empty shard) was not distinguished from passing evidence.

---

## 2. Selector Extraction Summary

**New module**: `spectrum_systems/modules/runtime/pr_test_selection.py`

This is the single source of truth for all PR test selection. It exposes:

| Function | Purpose |
|----------|---------|
| `is_governed_path(path)` | Delegates `_is_governed_changed_path` from preflight |
| `classify_changed_path(path)` | Classifies surface + governed flag |
| `resolve_governed_surfaces(paths)` | Filters to governed paths with metadata |
| `load_override_map(repo_root)` | Merges built-in + disk overrides |
| `resolve_required_tests(repo_root, paths)` | Maps each changed path to required tests |
| `assign_to_shard(test_path)` | Routes a test file to its owning shard |
| `is_docs_only_non_governed(paths)` | Decides whether empty selection is allowed |
| `build_selection_artifact(...)` | Constructs `pr_test_shard_selection` with fail-closed status |
| `compare_parity(ci_sel, pre_sel)` | Constructs `precheck_selection_parity` artifact |

**Preflight refactored**: `scripts/run_contract_preflight.py` now delegates:
- `_is_governed_changed_path` → `_canonical_is_governed_path`
- `_load_required_surface_override_map` → `_canonical_load_override_map`
- `resolve_required_surface_tests` → `_canonical_resolve_required_tests`

All fail-closed behavior in the existing preflight is preserved.

---

## 3. Shard Model Implemented

**Required shards (first stage, parallel)**:

| Shard | Coverage |
|-------|---------|
| `contract` | schemas, examples, standards-manifest, contract tests |
| `governance` | system registry, authority-shape, governance policy, preflight tests |
| `dashboard` | Jest/dashboard tests, MET-04-18 surfaces, dashboard artifacts |
| `changed_scope` | catch-all for tests selected by changed-path logic |

**Optional shards (deferred — not destabilizing PR)**:
- `runtime_core` — AEX/PQX/EVL/TPA/CDE/SEL tests
- `measurement` — SMA/MET/TLS/dashboard metrics tests

Deferral rationale: `runtime_core` and `measurement` contain deep integration tests that
are better verified in the nightly deep-gate workflow rather than on every PR, where false
positives could mask genuine governance failures in the required shards.

---

## 4. Workflow Changes

### `pr-pytest.yml` (modified)

Added two new jobs before the existing serial `pytest:` job:

1. **`shard-select`** — matrix job over `[contract, governance, dashboard, changed_scope]`
   - Runs `scripts/select_pr_test_shard.py` per shard
   - Executes selected tests via `python -m pytest`
   - Writes `outputs/pr_test_shards/<shard>/<shard>_result.json`
   - Uploads shard outputs as artifacts

2. **`pr-gate`** — aggregator, needs all shard-select jobs
   - Downloads all shard artifacts
   - Runs `scripts/run_pr_gate.py`
   - Writes `outputs/pr_gate/pr_gate_result.json`
   - Exits 1 if any required shard is missing, invalid, blocked, or failed

The existing `pytest:` job (preflight gate) remains **unchanged**.

### `nightly-deep-gate.yml` (new)

Runs at 03:00 UTC daily (+ `workflow_dispatch`). Executes:
- Full `python -m pytest tests/` suite
- Contract enforcement
- CI drift detector

This ensures `runtime_core` and `measurement` paths receive deep validation nightly.

---

## 5. 3LS Precheck Integration

All 3-letter systems that require test coverage must use the canonical selector. No 3LS
may implement its own selector. Integration points:

| System | Block condition |
|--------|----------------|
| AEX | Missing governed-surface coverage = admission block |
| PQX | Missing test coverage for execution slice = execution block |
| EVL | Missing required shard result = eval block |
| TPA | Missing governed-surface coverage = policy block |
| CDE | Missing shard evidence = block or human review |
| SEL | Missing/invalid shard artifacts = non-compliant input |

Documentation added to `docs/architecture/3ls_measurement_layer.md`.

---

## 6. Fail-Closed Invariants Added

| Invariant | Enforcer |
|----------|---------|
| Missing shard selection artifact → block | `run_pr_gate.py` |
| Invalid shard artifact JSON → block | `run_pr_gate.py` |
| Wrong artifact_type → block | `run_pr_gate.py` |
| `authority_scope != "observation_only"` → block | `run_pr_gate.py` |
| Governed surface + zero tests → block | `pr_test_selection.build_selection_artifact` |
| Shard selection status "block" → gate block | `run_pr_gate.py` |
| Shard result "fail" or "block" → gate block | `run_pr_gate.py` |
| Result "skipped" without `empty_allowed` selection → block | `run_pr_gate.py` |
| CI/precheck selection mismatch → block | `pr_test_selection.compare_parity` |
| New test without shard mapping → drift finding | `run_ci_drift_detector.py` |
| Missing schema/example → drift block | `run_ci_drift_detector.py` |
| Workflow bypasses canonical selector → drift block | `run_ci_drift_detector.py` |

---

## 7. Red-Team Findings and Fix Dispositions

Full review: `docs/reviews/PAR-00-01_parallel_pr_tests_redteam.md`
Full fix manifest: `docs/review-actions/PAR-00-01_fix_actions.md`

| Finding | Severity | Disposition |
|---------|---------|-------------|
| RT-01: Missing shard artifact treated as pass | must_fix | fixed |
| RT-02: Invalid shard JSON treated as pass | must_fix | fixed |
| RT-03: Governed surface selects zero tests | must_fix | fixed |
| RT-04: New test file lacks shard mapping | must_fix | fixed |
| RT-05: Governance shard skipped for governance changes | must_fix | fixed |
| RT-06: Authority-shape bypass via shard result | must_fix | fixed |
| RT-07: Shard claims certification/enforcement authority | must_fix | fixed |
| RT-08: Aggregator reimplements selection logic | must_fix | fixed |
| RT-09: Dashboard passes while governance fails, gate allows | should_fix | fixed (AND aggregation) |
| RT-10: CI and precheck diverge silently | should_fix | fixed (parity artifact) |
| RT-11: runtime_core/measurement deferred, deep validation removed | should_fix | fixed (nightly workflow) |
| RT-12: Matrix cancellation hides failure | observation | acknowledged |
| RT-13: Shard writes to shared output path | observation | acknowledged |
| RT-14: Nightly deep workflow removed | observation | fixed (nightly workflow created) |

**No unresolved must_fix findings.**

---

## 8. Tests Run

New test files:
- `tests/test_pr_test_selection_engine.py` — 24 tests for canonical selector
- `tests/test_pr_test_shards.py` — 8 tests for shard artifact schema
- `tests/test_pr_gate_parallel.py` — 10 tests for aggregator fail-closed behavior
- `tests/test_ci_drift_detector.py` — 6 tests for drift detector

Governance policy updated:
- `docs/governance/pytest_pr_selection_integrity_policy.json` — 4 new surface rules
- `docs/governance/preflight_required_surface_test_overrides.json` — 4 new entries

Validation commands:
```bash
python -m pytest tests/test_pr_test_selection_engine.py tests/test_pr_test_shards.py \
  tests/test_pr_gate_parallel.py tests/test_ci_drift_detector.py -q

python -m pytest tests/ -k "pr_test or shard or selection or contract_preflight or ci_drift" -q
```

---

## 9. Expected Runtime Improvement

| Phase | Before | After |
|-------|--------|-------|
| Shard selection (CI) | serial (inside preflight) | parallel across 4 shards |
| Shard test execution | serial (all tests in one job) | parallel across 4 matrix jobs |
| First failing shard visibility | end of serial run | ~4 min (first shard to fail) |
| Total PR test wall time | 15+ min | ~4-8 min (bounded by slowest shard) |

The nightly deep-gate preserves full coverage without penalizing PR latency.

---

## 10. Remaining Risks

1. **Shard imbalance**: `changed_scope` can become a catch-all absorbing large test sets.
   Mitigation: Monitor `coverage_ratio` in selection artifacts; rebalance patterns if needed.

2. **Matrix cancellation**: GitHub Actions matrix cancellation on `fail-fast: true` can hide
   which other shards would have failed. Mitigated by `fail-fast: false` in the matrix.

3. **New governed surfaces without shard mapping**: Drift detector catches this but only on
   nightly runs. Recommend adding drift detector to the PR workflow as an informational step.

4. **Precheck parity**: The parity artifact is only produced if both CI and precheck modes are
   run. In local/precheck-only flows, parity is not enforced. CDE and TPA must explicitly
   require the parity artifact when governing repo-mutating work.

---

## 11. Recommended Next Prompt

```
PAR-00-02 — Add drift detector as an informational shard in the PR workflow matrix so
unmapped tests are detected on every PR rather than nightly only. Also add runtime_core
and measurement shards as non-blocking informational jobs in the first stage, feeding
their results into the nightly deep-gate aggregator for trend analysis.
```
