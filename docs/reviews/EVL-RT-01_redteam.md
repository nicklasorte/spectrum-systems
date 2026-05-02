# EVL-RT-01 Red-Team — PR Test Runtime Budget Observation

Scope: red-team review of the EVL-RT-01 slice. EVL-RT-01 adds a narrow
observation-only artifact, `pr_test_runtime_budget_observation`, that
records selected tests, shard durations, slowest shard, fallback /
full-suite usage, the configured runtime budget, the resulting
`budget_status`, reason codes, and operator-facing improvement
recommendations. The artifact is built by
`scripts/build_pr_test_runtime_budget_observation.py` and consumes the
existing `pr_test_shards_summary` and `selection_coverage_record`
artifacts. The builder does not run pytest, mutate selection, duplicate
selector logic, change PR policy, weaken existing tests, or block PRs.

Authority boundary preserved: the artifact is `observation_only`. EVL
retains canonical authority over eval acceptance and dataset semantics
per `docs/architecture/system_registry.md`. The shard runner
(`scripts/run_pr_test_shards.py`) and the canonical PR test selector
(`spectrum_systems/modules/runtime/pr_test_selection.py`) remain the
sole owners of test execution and selection. The runtime budget
observation never holds admission, execution closure, eval evidence,
policy, continuation, or final-gate signal.

## Authority-safe vocabulary

This document avoids reserved owner-authority verbs and their negated
forms. The runtime budget artifact emits runtime, fallback, and
recommendation observations only. It does not approve, certify,
promote, enforce, decide, or authorize anything.

## Threat scenarios

### 1. Runtime artifact claims complete with no shard refs

Disposition: **closed**.
Mechanism: the schema requires `shard_result_refs.minItems >= 1`
whenever `shard_summary_ref` is a non-null string. The builder also
appends the supplied `shard_summary_ref` into `shard_result_refs` after
reading it, so a present shard summary always carries an artifact ref.
When the shard summary cannot be loaded, `shard_summary_ref` is set to
`null` and `shard_result_refs` may be empty — the conditional `if`
branch is not triggered, but `budget_status` becomes `unknown` and the
required `reason_codes` minItems rule applies.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_present_shard_summary_requires_shard_result_refs`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_records_slowest_shard_and_durations_from_summary`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_unknown_when_summary_missing_carries_reason_codes`.

### 2. Unknown runtime state silently treated as within budget

Disposition: **closed**.
Mechanism: `budget_status=unknown` requires `reason_codes.minItems >=
1`. The builder always emits at least one of
`shard_summary_artifact_missing`,
`total_duration_seconds_missing`,
`runtime_budget_seconds_missing`,
`shard_summary_total_duration_missing`,
or `selection_coverage_artifact_missing` whenever an input is missing
or unreadable. There is no public code path that yields
`budget_status=unknown` with empty `reason_codes`.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_unknown_budget_status_requires_reason_codes`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_unknown_when_summary_missing_carries_reason_codes`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_unknown_when_runtime_budget_missing`.

### 3. Full-suite fallback hidden from operators

Disposition: **closed**.
Mechanism: `full_suite_detected=true` is a conditional that requires
`fallback_reason_codes.minItems >= 1`. The builder's
`_detect_full_suite` helper inspects three signals — selected target
tokens (`tests`, `tests/`, `.`), selection reason codes containing
known full-suite tokens (`fallback_full_suite`, `select_all_tests`,
`no_governed_paths_matched`), and fallback target tokens — and always
populates at least one fallback reason code when any is present. The
artifact also emits a `full_suite_fallback_observed` improvement
recommendation in the same flow.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_full_suite_detected_requires_fallback_reason_codes`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_records_full_suite_when_selected_target_is_tests_dir`.

### 4. Slow shard hidden from operators

Disposition: **closed**.
Mechanism: the builder always reads `slowest_shard` and
`max_shard_duration_seconds` from the canonical
`pr_test_shards_summary` and writes them as
`slowest_shard` / `slowest_shard_duration_seconds` on the artifact.
When timing is present, the builder also emits a
`slowest_shard_observed` improvement recommendation that names the
shard explicitly. The schema records both fields on every artifact.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_builder_records_slowest_shard_and_durations_from_summary`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_reuses_canonical_summary_timing`.

### 5. No reason codes on unknown / over-budget runs

Disposition: **closed**.
Mechanism: schema conditionals require `reason_codes.minItems >= 1`
when `budget_status` is `unknown` or `over_budget`. The builder writes
`total_duration_seconds_over_runtime_budget` whenever the measured
total exceeds the configured budget, and writes one or more
missing-input reason codes when inputs are unreadable.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_over_budget_status_requires_reason_codes`,
`tests/test_pr_test_runtime_budget_observation.py::test_unknown_budget_status_requires_reason_codes`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_records_over_budget_with_reason_code`.

### 6. Artifact mutates selection instead of observing it

Disposition: **closed**.
Mechanism: the builder reads the existing `selection_coverage_record`
and `pr_test_shards_summary` artifacts only. It does not import the
canonical selector module, does not write to `tests/`, does not modify
`docs/governance/preflight_required_surface_test_overrides.json`, and
does not invoke pytest or `subprocess`. The PR-test workflow is
unchanged by this slice.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_builder_does_not_invoke_subprocess_or_pytest`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_does_not_mutate_selector_module`.

### 7. Duplicate selector logic introduced

Disposition: **closed**.
Mechanism: the builder consumes the already-emitted
`selection_coverage_record` artifact for `changed_paths`,
`selected_test_targets`, `fallback_used`, `fallback_targets`, and
`selection_reason_codes`. It does not redefine `assign_to_shard`,
`resolve_required_tests`, `resolve_governed_surfaces`, or
`build_selection_coverage_record`. The test suite asserts that the
builder source contains none of those entrypoints and does not import
the canonical selector module at all.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_builder_does_not_mutate_selector_module`.

### 8. Measurement layer claims authority

Disposition: **closed**.
Mechanism: every artifact, schema, and example records
`authority_scope = observation_only`. The schema fixes that field with
a `const`. The artifact has no `block`, `pass/fail` gate field; the
only status field is `budget_status` whose values
(`within_budget`, `over_budget`, `unknown`) are observation outcomes.
Improvement recommendations carry `observation_only: true` (also a
`const` in the schema) and are documented as operator-facing only —
they never reassign tests, change selection, or block PRs.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_example_authority_scope_is_observation_only`,
`tests/test_pr_test_runtime_budget_observation.py::test_authority_scope_must_be_observation_only`,
`tests/test_pr_test_runtime_budget_observation.py::test_recommendations_are_observation_only`.

### 9. Authority vocabulary regression

Disposition: **closed**.
Mechanism: the test suite scans the schema, example, and builder for
any reserved authority token (approve, certify, promote, enforce,
decide, authorize, verdict, …). Adding a token causes a CI failure,
preventing accidental authority drift in this artifact.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_artifact_files_use_authority_safe_vocabulary`.

### 10. Coverage reduction smuggled in under measurement

Disposition: **closed**.
Mechanism: this slice adds a schema, an example, a manifest entry, a
builder script, a test module, and two review docs. It does not delete
or rename any test file, any selector entrypoint, any shard runner
behavior, any required-shards configuration, the `pr-pytest.yml`
workflow, the `core_loop_pre_pr_gate_policy.json`, or the override
policy. Existing required tests, full-suite validation on
main/scheduled workflows, and PR shard policy are unchanged.

### 11. Fallback used but no fallback signal

Disposition: **closed**.
Mechanism: `_detect_full_suite` ensures that whenever
`fallback_used=true`, at least one `fallback_reason_codes` entry is
emitted — either a token-derived signal or, as a fail-safe,
`fallback_target:<value>` for each fallback target, and finally
`selector_reported_fallback_used` if no other code applies. The schema
also enforces this at validation time.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_fallback_used_requires_fallback_reason_codes`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_records_fallback_when_selector_reports_fallback_only`.

## Residual weak seam

The runtime budget value is supplied via the builder's
`--runtime-budget-seconds` flag with a conservative default of
`300.0`. There is no governed policy artifact yet that records the
canonical budget; an operator could choose any value when invoking the
builder. This is intentional for the EVL-RT-01 slice — the artifact is
observation-only, so a different budget changes the recorded
`budget_status` but does not block PRs or change CI behavior.
A follow-up slice can add a governed budget policy artifact and feed
its value into the builder once operator practice is established.

The other residual seam is that the artifact does not yet feed any
downstream consumer (APR, CLP, dashboard). Wiring it into a consumer is
out of scope for the EVL-RT-01 measurement slice and would be added in
a separate downstream-consumer slice if and when needed.
