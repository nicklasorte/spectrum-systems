# EVL-RT-03 Red-Team — Shard-First PR Readiness Observation

Scope: red-team review of the EVL-RT-03 slice. EVL-RT-03 adds an
observation-only `pr_test_shard_first_readiness_observation` artifact
plus a builder
(`scripts/build_pr_test_shard_first_readiness_observation.py`) and an
APR EVL-phase consumer check
(`evl_pr_test_shard_first_readiness` in `scripts/run_agent_pr_precheck.py`).
The artifact records, for a PR's already-measured shard run, whether
the PR path is `shard_first` (focused selection backed by required
shard evidence refs) or `fallback_justified` (broad/full-suite usage
explained by the existing `fallback_justification` section in
`pr_test_runtime_budget_observation`). The slice does not change CI
behavior, does not run pytest, does not mutate test selection, and
does not weaken existing required tests or full-suite validation. It
does not touch PRL/F3L runtime, APU PRL evidence policy, the
dashboard, or the `pr-pytest.yml` workflow.

Authority boundary preserved: the artifact is `observation_only`. EVL
retains canonical authority over eval acceptance and dataset semantics
per `docs/architecture/system_registry.md`. The shard runner
(`scripts/run_pr_test_shards.py`) and the canonical PR test selector
(`spectrum_systems/modules/runtime/pr_test_selection.py`) remain the
sole owners of test execution and selection. The shard-first readiness
artifact never holds admission, execution closure, eval evidence,
policy, continuation, or final-gate signal — it is a readiness
observation that APR aggregates alongside other observation-only
inputs.

## Authority-safe vocabulary

This document avoids reserved owner-authority verbs and their negated
forms. The shard-first readiness observation emits readiness, runtime,
fallback, and shard-first observations only. It does not provide
review observation, advance recommendation, surface compliance
observation, or control input on behalf of any canonical owner.
Recommended mapping candidates and recommended shard candidates are
operator-facing observations and never reassign tests or change
selection.

## Threat scenarios

### 1. Broad pytest path with no fallback justification

Disposition: **closed**.
Mechanism: the schema rule requires `fallback_used=true` to carry a
non-null `fallback_justification_ref` AND `fallback_reason_codes`
minItems 1. The schema rule for `full_suite_detected=true` carries the
same requirement. The classifier in
`build_pr_test_shard_first_readiness_observation._classify_shard_first_status`
returns `fallback_justified` only when (a) the runtime budget
observation is present, (b) the `fallback_justification` section is
present, (c) upstream `fallback_reason_codes` is non-empty, and (d) a
non-null `fallback_justification_ref` is recorded; otherwise it
returns `partial` with reason codes. The APR consumer
(`evl_pr_test_shard_first_readiness`) maps the readiness status:
`shard_first` and `fallback_justified` → APR `pass`; `partial` /
`missing` / `unknown` → APR `block` with the readiness reason codes
preserved.
Tests:
`tests/test_pr_test_shard_first_readiness_observation.py::test_fallback_justified_requires_fallback_justification_ref`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_fallback_justified_requires_fallback_reason_codes`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_fallback_used_true_requires_fallback_justification_ref`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_full_suite_detected_true_requires_fallback_justification_ref`,
`tests/test_agent_pr_precheck.py::test_evl_pr_test_shard_first_readiness_blocks_when_required_shard_missing`,
`tests/test_agent_pr_precheck.py::test_evl_pr_test_shard_first_readiness_blocks_on_unjustified_full_suite`.

### 2. Fallback justification exists but has no reason codes

Disposition: **closed**.
Mechanism: the schema rule requires `fallback_used=true`, the
`fallback_justified` status, and `full_suite_detected=true` to each
carry `fallback_reason_codes` minItems 1. The classifier never returns
`fallback_justified` when upstream `fallback_reason_codes` is empty;
it returns `partial` and surfaces `fallback_reason_codes_missing` in
the readiness `reason_codes`. The fail-closed synthesis path adds a
`fallback_used_observed_without_upstream_reason_codes` (or
`full_suite_detected_observed_without_upstream_reason_codes`) entry to
`fallback_reason_codes` AFTER classification so the readiness artifact
satisfies the schema while making the upstream gap visible — the
`fallback_justified` path is never reached when upstream reason codes
are absent.
Tests:
`tests/test_pr_test_shard_first_readiness_observation.py::test_fallback_justified_requires_fallback_reason_codes`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_partial_when_fallback_used_with_no_reason_codes`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_classifies_partial_when_fallback_used_but_justification_missing`.

### 3. Shard-first status claimed with no shard refs

Disposition: **closed**.
Mechanism: the schema rule for
`shard_first_status=shard_first` requires `required_shard_refs`
minItems 1, `fallback_used=false`, and `full_suite_detected=false`.
The classifier requires a non-empty `required_shard_refs` list before
returning `shard_first`; missing/failed required shards yield
`partial`. The builder reads `required_shards` and `shard_status` from
the canonical `pr_test_shards_summary` artifact only — it never
reconstructs shard membership from selection logic.
Tests:
`tests/test_pr_test_shard_first_readiness_observation.py::test_shard_first_status_requires_required_shard_refs`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_shard_first_status_forbids_fallback_used`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_shard_first_status_forbids_full_suite_detected`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_classifies_shard_first_when_required_refs_present`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_classifies_partial_when_required_shard_status_missing`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_classifies_partial_when_required_shard_failed`.

### 4. Unknown state treated as clean

Disposition: **closed**.
Mechanism: the schema rule for `shard_first_status=unknown` requires
`reason_codes` minItems 1. The classifier returns `unknown` only when
the runtime budget observation is missing while shard summary is
present (so fallback status cannot be proven). It always emits a reason
code (`runtime_budget_observation_missing_cannot_prove_shard_first`).
Similarly `missing` and `partial` always emit reason codes. The APR
consumer maps `unknown` → APR `block`.
Tests:
`tests/test_pr_test_shard_first_readiness_observation.py::test_unknown_status_requires_reason_codes`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_missing_status_requires_reason_codes`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_partial_status_requires_reason_codes`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_classifies_unknown_when_runtime_budget_missing`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_classifies_missing_when_summary_and_runtime_budget_absent`.

### 5. PR prose counted as fallback evidence

Disposition: **closed**.
Mechanism: the schema requires `fallback_justification_ref` to be a
string with `minLength` 1 whenever `shard_first_status=fallback_justified`,
`fallback_used=true`, or `full_suite_detected=true`. Free-text PR
descriptions cannot be encoded as `fallback_justification_ref`. The
APR consumer surfaces the readiness artifact ref in
`output_artifact_refs`; the readiness artifact ref points at a JSON
file that itself references `runtime_budget_observation_ref` and
`shard_summary_ref` artifacts on disk.
Tests:
`tests/test_pr_test_shard_first_readiness_observation.py::test_pr_prose_does_not_satisfy_fallback_evidence`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_fallback_justified_requires_fallback_justification_ref`.

### 6. Builder runs pytest

Disposition: **closed**.
Mechanism: the builder is consumption-only. It reads the existing
`pr_test_shards_summary`, `selection_coverage_record`, and
`pr_test_runtime_budget_observation` artifacts and emits a single JSON
file. The test suite scans the builder source for `subprocess`,
`pytest`, `os.system`, and equivalent execution patterns and asserts
none are present. The PR-test workflow is unchanged by this slice. The
APR consumer wraps the builder in-process; it never spawns a pytest
subprocess.
Tests:
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_does_not_invoke_subprocess_or_pytest`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_does_not_mutate_shard_runner`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_does_not_mutate_runtime_budget_builder`.

### 7. Selector logic duplicated

Disposition: **closed**.
Mechanism: the builder consumes already-emitted artifacts. It does not
import the canonical selector module (`pr_test_selection`), does not
re-execute `assign_to_shard`, `resolve_required_tests`,
`resolve_governed_surfaces`, or `build_selection_coverage_record`, and
does not import the runtime budget builder. It only re-emits already-
recorded mapping candidates and shard candidates from the upstream
runtime budget `fallback_justification` section, with each candidate
forced to `observation_only=true`. The test suite asserts the builder
source contains none of those entrypoints and does not import the
canonical selector or runtime budget builder modules.
Tests:
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_does_not_mutate_selector_module`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_does_not_mutate_shard_runner`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_does_not_mutate_runtime_budget_builder`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_builder_reuses_fallback_justification_recommended_candidates`.

### 8. Tests weakened or removed

Disposition: **closed**.
Mechanism: this slice adds a schema, example, manifest entry,
builder, APR consumer check, two test files (one new module and three
new APR test cases), and two review docs. It does not delete or
rename any existing test file, any selector entrypoint, any shard
runner behavior, any required-shards configuration, the `pr-pytest.yml`
workflow, the `core_loop_pre_pr_gate_policy.json`, or the override
policy. Existing required tests, full-suite validation on
main / scheduled workflows, and PR shard policy are unchanged. The
EVL-RT-01 / EVL-RT-02 test suites continue to pass without
modification.
Tests:
`tests/test_pr_test_runtime_budget_observation.py` (existing suite),
`tests/test_selection_coverage_record.py` (existing suite),
`tests/test_pr_test_shards.py` (existing suite),
`tests/test_agent_pr_precheck.py` (existing + new EVL-RT-03 cases).

### 9. Measurement layer claims authority

Disposition: **closed**.
Mechanism: `authority_scope` remains `observation_only` (a `const` in
the schema) on the artifact. The artifact has no gate, status, or
owner-authority fields drawn from the canonical reserved-vocabulary
token list maintained in
`tests/test_pr_test_shard_first_readiness_observation.py`
(`_FORBIDDEN_AUTHORITY_TOKENS`). Its only categorical field is
`shard_first_status` whose values (`shard_first`, `fallback_justified`,
`missing`, `partial`, `unknown`) are observation outcomes.
Recommended mapping candidates and recommended shard candidates carry
`observation_only: true` (also a `const` in the schema) and are
documented as operator-facing only — they never reassign tests, change
selection, change shard composition, or block PRs. The APR consumer
maps the readiness status to its own `pass` / `block` rollups for the
EVL phase; ownership of admission, execution closure, eval evidence,
policy, continuation, and final-gate signal remains with the
canonical owners listed in `docs/architecture/system_registry.md`.
Tests:
`tests/test_pr_test_shard_first_readiness_observation.py::test_example_authority_scope_is_observation_only`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_authority_scope_must_be_observation_only`,
`tests/test_pr_test_shard_first_readiness_observation.py::test_recommended_candidates_are_observation_only`.

### 10. Authority vocabulary regression

Disposition: **closed**.
Mechanism: a dedicated test scans the schema, example, and builder for
the canonical reserved owner-authority token list maintained in the
shard-first readiness test module (`_FORBIDDEN_AUTHORITY_TOKENS`).
Adding any listed token to those files causes a CI finding, preventing
accidental authority drift in this artifact. The token list is the
single source of truth and is not re-enumerated here so this review
document remains within authority-safe wording. The existing
`test_no_banned_authority_tokens_in_apr_owned_files` test continues to
scan the APR runner.
Tests:
`tests/test_pr_test_shard_first_readiness_observation.py::test_artifact_files_use_authority_safe_vocabulary`,
`tests/test_agent_pr_precheck.py::test_no_banned_authority_tokens_in_apr_owned_files`.

## Residual weak seam

The shard-first readiness observation is observation-only. It is now
consumed as an EVL-phase readiness input by APR
(`evl_pr_test_shard_first_readiness`), which surfaces the status into
APR's overall pass/block rollup; APU and CLP do not consume it
directly yet, and the dashboard does not surface it. Wiring the
readiness ref into APU PRL evidence or the CLP allowed warn reason
code list is intentionally out of scope for this slice and would be
added in a separate downstream-consumer slice if and when needed. The
runtime budget value is still supplied via the runtime budget
builder's `--runtime-budget-seconds` flag with a conservative default
of `300.0` (see EVL-RT-01 / EVL-RT-02 residual seam); no governed
policy artifact yet records the canonical budget value.
