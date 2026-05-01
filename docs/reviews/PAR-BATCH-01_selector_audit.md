# PAR-BATCH-01 — Selector Audit

This audit captures the state of the PR test selection / shard machinery
as of the start of PAR-BATCH-01. It is a measurement observation, not an
authority claim. Canonical ownership remains with the systems declared in
`docs/architecture/system_registry.md`.

## 1. Current selector files

| File | Role |
|------|------|
| `spectrum_systems/modules/runtime/pr_test_selection.py` | Canonical selector module. Defines `SHARD_NAMES`, `SHARD_PATH_PATTERNS`, `assign_to_shard`, `resolve_required_tests`, `build_selection_artifact`, `compare_parity`. authority_scope: observation_only. |
| `scripts/select_pr_test_shard.py` | CLI wrapper that produces a `pr_test_shard_selection` artifact for a single shard given `--mode {ci,precheck}`, `--shard`, `--base-ref`, `--head-ref`. |
| `scripts/run_pr_gate.py` | Aggregator that loads per-shard `pr_test_shard_selection` and `pr_test_shard_result` artifacts and emits `pr_gate_result`. Aggregates only — does not recompute selection. |
| `.github/workflows/pr-pytest.yml` | Runs the matrix `[contract, governance, dashboard, changed_scope]`, calls `select_pr_test_shard.py`, then runs pytest inline and writes a `pr_test_shard_result` artifact. |

## 2. Current override files

| File | Role |
|------|------|
| `docs/governance/preflight_required_surface_test_overrides.json` | Path → required test bindings. Merged on top of the in-process `_REQUIRED_SURFACE_TEST_OVERRIDES` baked into `pr_test_selection.py`. |
| `docs/governance/pytest_pr_selection_integrity_policy.json` | Surface rules for `path_prefix → required_test_targets` consumed by `run_contract_preflight.py`'s integrity check. |

## 3. Current required test mapping behavior

`resolve_required_tests(repo_root, changed_paths)` returns a per-path
dictionary of required test files. For each changed path:

1. Pull explicit overrides from the merged override map.
2. If the path is itself a `tests/test_*.py` file, include it.
3. Otherwise, scan all `tests/test_*.py` files for substring matches of
   the changed path's stem / basename.

`assign_to_shard(test_path)` then maps each test file to a shard via the
`SHARD_PATH_PATTERNS` table. `changed_scope` is the catch-all and is
absorbed by `select_pr_test_shard.py`'s `_select_tests_for_shard` for any
test that isn't routed to one of the four required PR shards (contract,
governance, dashboard, changed_scope).

## 4. How APR currently invokes selected tests

`scripts/run_agent_pr_precheck.py` performs two pytest-related checks:

1. `aex_required_surface_check` — uses `resolve_required_tests` and the
   override map directly to detect governed paths whose required-surface
   mapping is empty. Emits `MISSING_REQUIRED_SURFACE_MAPPING` and
   `unmapped:<path>` reason codes.
2. `evl_selected_tests` — re-resolves required tests for governed
   changed paths and runs them via a single `pytest -q <targets>` call.
   Writes `apr_evl_selected_tests_observation`.

APR does NOT currently invoke `select_pr_test_shard.py`, does NOT shard
the run, and does NOT emit per-shard artifacts. The whole selected-test
set runs in one process.

## 5. Where `pytest_selection_missing` is produced

`pytest_selection_missing` reason codes originate inside
`scripts/run_contract_preflight.py` when its integrity check sees a
governed surface change with an empty `selected_test_files`. The same
class of failure surfaces in APR through:

- `aex_required_surface_check` → `MISSING_REQUIRED_SURFACE_MAPPING` /
  `unmapped:<path>`
- `pqx_governed_contract_preflight` → reason code
  `contract_mismatch` (when preflight itself blocks)

## 6. Current gaps surfaced by recent smoke PRs

- **Selection layer is implicit.** APR re-resolves test targets in two
  separate places (AEX phase + EVL phase) instead of calling a single
  shard runner that emits artifact-backed evidence.
- **No per-shard artifact in the precheck path.** The CI workflow emits
  one `pr_test_shard_result` per matrix entry, but APR (which is
  precheck-only) emits only `apr_evl_selected_tests_observation`. The
  pre-PR readiness signal therefore diverges from the CI shard signal.
- **`unknown` is not a first-class status.** The current schema enum is
  `pass | fail | block | skipped`. There is no `missing` or `unknown`
  status, so a shard whose selection / runner output is absent has to be
  inferred from a missing file rather than from an explicit status.
- **`pass` does not require artifact refs.** A shard with `status=pass`
  could omit `output_artifact_refs`, so a green signal without backing
  evidence is currently representable.
- **Reason codes are not tied to non-pass statuses in the schema.**
  `failure_summary` is required only when `status` is `fail` / `block`.
  `skipped` carries no required reason.
- **Selector vocabulary is split.** `pr_test_selection.SHARD_NAMES`
  exposes `dashboard`; the broader runtime calls these "generated
  artifacts" tests. The shard names should converge before CI is
  parallelized.
- **APR has no shard artifact refs.** Without per-shard refs in
  `agent_pr_precheck_result`, downstream consumers (M3L, APU) cannot
  cite a shard-level evidence chain.

## 7. Direction for PAR-BATCH-01

PAR-BATCH-01 makes the selection layer artifact-backed and exposes a
sequential shard runner that APR consumes. Concretely:

1. Tighten the `pr_test_shard_result` schema so:
   - the status enum is `pass | fail | skipped | missing | unknown`,
   - `pass` requires `output_artifact_refs`,
   - `fail | missing | unknown | skipped` require `reason_codes`,
   - the artifact records `command`, `exit_code`, `duration_seconds`,
     and `created_at`.
2. Add a sequential shard runner (`scripts/run_pr_test_shards.py`) that
   reuses the canonical selector, runs each shard in process, and
   writes one artifact per shard plus a compact summary.
3. Rewire APR's EVL phase to invoke the shard runner instead of running
   `pytest -q` once over the union of selected tests. Emit shard
   artifact refs in `agent_pr_precheck_result.selected_test_refs`.
4. Define canonical shards `contract`, `governance`, `runtime_core`,
   `changed_scope`, `generated_artifacts`, `measurement`. The legacy
   `dashboard` shard maps to `generated_artifacts` inside the new
   runner; the existing selector's `SHARD_NAMES` is left untouched so
   the existing CI matrix keeps working until PAR-CI-01 migrates it.
5. No GitHub workflow changes in this slice. Parallelization is deferred
   to PAR-CI-01.

This reduces future parallelization risk because the artifact-backed
shard contract — not workflow YAML — becomes the canonical source of
truth for what ran in each shard. The CI matrix can be rewired without
re-deriving any selection logic.
