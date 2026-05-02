# EVL-RT-02 Red-Team — PR Test Fallback Justification Observation

Scope: red-team review of the EVL-RT-02 slice. EVL-RT-02 extends the
existing observation-only `pr_test_runtime_budget_observation` artifact
with a `fallback_justification` section that records why broad /
full-suite / shard fallback was used, what evidence triggered it
(`selection_coverage_ref`, `shard_summary_ref`, `unmatched_changed_paths`,
`missing_surface_mappings`), what tests were selected, and which mapping
or sharding improvements should be considered. The section is
reason-coded, refs the canonical `selection_coverage_record` and
`pr_test_shards_summary` artifacts, and never claims authority over
selection, sharding, or PR admission.

The slice does not change CI behavior, does not run pytest, does not
mutate test selection, and does not weaken existing required tests or
full-suite validation. It does not touch PRL/F3L runtime, APU/CLP
policy, the dashboard, or the `pr-pytest.yml` workflow.

Authority boundary preserved: the artifact remains `observation_only`.
EVL retains canonical authority over eval acceptance and dataset
semantics per `docs/architecture/system_registry.md`. The shard runner
(`scripts/run_pr_test_shards.py`) and the canonical PR test selector
(`spectrum_systems/modules/runtime/pr_test_selection.py`) remain the
sole owners of test execution and selection. The fallback justification
section never holds admission, execution closure, eval evidence,
policy, continuation, or final-gate signal.

## Authority-safe vocabulary

This document avoids reserved owner-authority verbs and their negated
forms. The fallback justification section emits fallback-scope,
mapping, and shard observations only. It does not provide review
observation, readiness evidence, advance recommendation, surface
compliance observation, or control input on behalf of any canonical
owner. Recommended mapping candidates and recommended shard candidates
are operator-facing observations and never reassign tests or change
selection.

## Threat scenarios

### 1. Fallback used with no reason codes

Disposition: **closed**.
Mechanism: the schema requires
`fallback_justification.fallback_reason_codes.minItems >= 1` whenever
`fallback_justification.fallback_used` is `true`. The builder reuses
the existing `_detect_full_suite` helper to populate the shared
`fallback_reason_codes` list (token-derived signals, fallback target
echoes, or `selector_reported_fallback_used`) and copies that list into
the justification section. There is no public path that yields
`fallback_used=true` with empty `fallback_reason_codes`.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_fallback_justification_fallback_used_true_requires_reason_codes`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_classifies_full_suite_scope_with_evidence_refs`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_classifies_broad_pytest_scope_for_select_all_tests`.

### 2. Full-suite detected but hidden

Disposition: **closed**.
Mechanism: the schema enforces
`fallback_justification.full_suite_detected=true` requires
`fallback_reason_codes.minItems >= 1` and requires at least one of
`selection_coverage_ref` or `shard_summary_ref`. The builder always
populates these when full-suite signals are observed (selected target
tokens, selection reason codes, or fallback target tokens) and always
records a `recommended_shard_candidates` entry with action
`narrow_selection` when scope is `full_suite`.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_fallback_justification_full_suite_detected_requires_reason_codes`,
`tests/test_pr_test_runtime_budget_observation.py::test_fallback_justification_full_suite_present_requires_evidence_ref`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_emits_recommended_shard_candidates_for_full_suite_scope`.

### 3. Unknown fallback state treated as clean

Disposition: **closed**.
Mechanism: the schema enforces
`fallback_justification.fallback_scope=unknown` requires
`fallback_reason_codes.minItems >= 1`. The builder's
`_classify_fallback_scope` helper returns `unknown` only when
`selection_coverage` is missing (or both inputs are missing) and always
emits at least one reason code
(`fallback_scope_unknown_inputs_missing` or
`fallback_scope_unknown_selection_coverage_missing`). The conditional
prevents an `unknown` scope from passing schema validation as a clean
`none` scope.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_fallback_justification_unknown_scope_requires_reason_codes`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_classifies_unknown_scope_when_inputs_missing`.

### 4. Missing selection refs counted present

Disposition: **closed**.
Mechanism: the schema enforces that whenever
`fallback_justification.fallback_used` or
`fallback_justification.full_suite_detected` is `true`, the section
must include at least one of `selection_coverage_ref` or
`shard_summary_ref` (each with `minLength >= 1`). The builder uses the
filesystem path of the loaded selection coverage record (or `None` when
the coverage artifact is missing). If selection coverage is missing the
classifier returns `unknown` (covered by scenario 3) so a present
fallback claim cannot be recorded without a backing ref.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_fallback_justification_present_fallback_requires_evidence_ref`,
`tests/test_pr_test_runtime_budget_observation.py::test_fallback_justification_full_suite_present_requires_evidence_ref`.

### 5. Fallback justification mutates test selection

Disposition: **closed**.
Mechanism: the builder reads the existing `selection_coverage_record`
artifact only — it never imports the canonical selector module, never
writes to `tests/`, never writes to
`docs/governance/preflight_required_surface_test_overrides.json`, and
never invokes `subprocess` or `pytest`. The
`recommended_mapping_candidates` and `recommended_shard_candidates`
fields are observation-only (forced `observation_only=true` in the
schema and at copy-time in the builder); they never reassign tests,
mutate selection, or change sharding.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_fallback_justification_does_not_mutate_selection_or_run_pytest`,
`tests/test_pr_test_runtime_budget_observation.py::test_builder_surfaces_recommended_mapping_candidates_observation_only`.

### 6. Builder runs pytest

Disposition: **closed**.
Mechanism: the builder is consumption-only. It reads the existing
`pr_test_shards_summary` and `selection_coverage_record` artifacts and
emits a single JSON file. The test suite scans the builder source for
`subprocess`, `pytest`, `os.system`, and equivalent execution patterns
and asserts none are present. The PR-test workflow is unchanged by
this slice.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_builder_does_not_invoke_subprocess_or_pytest`,
`tests/test_pr_test_runtime_budget_observation.py::test_fallback_justification_does_not_mutate_selection_or_run_pytest`.

### 7. Duplicate selector logic introduced

Disposition: **closed**.
Mechanism: the builder consumes the already-emitted
`selection_coverage_record` artifact for `changed_paths`,
`selected_test_targets`, `fallback_used`, `fallback_targets`,
`selection_reason_codes`, `unmatched_changed_paths`,
`attempted_surface_rules`, and `recommended_mapping_candidates`. It
does not redefine `assign_to_shard`, `resolve_required_tests`,
`resolve_governed_surfaces`, or `build_selection_coverage_record`. The
fallback scope classifier reads selector-emitted signals and never
re-runs the selector. The test suite asserts that the builder source
contains none of those entrypoints and does not import the canonical
selector module at all.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_builder_does_not_mutate_selector_module`,
`tests/test_pr_test_runtime_budget_observation.py::test_fallback_justification_does_not_mutate_selection_or_run_pytest`.

### 8. Measurement layer claims authority

Disposition: **closed**.
Mechanism: `authority_scope` remains `observation_only` (a `const` in
the schema) on the artifact. The fallback justification section has no
`block`, `pass/fail`, `verdict`, `approval`, or `enforcement` fields;
its only categorical field is `fallback_scope` whose values
(`none`, `shard_fallback`, `broad_pytest`, `full_suite`, `unknown`) are
observation outcomes. Recommended mapping candidates and recommended
shard candidates carry `observation_only: true` (also a `const` in the
schema) and are documented as operator-facing only — they never
reassign tests, change selection, change shard composition, or block
PRs.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_fallback_justification_authority_scope_preserved`,
`tests/test_pr_test_runtime_budget_observation.py::test_fallback_justification_section_required_in_schema`,
`tests/test_pr_test_runtime_budget_observation.py::test_authority_scope_must_be_observation_only`.

### 9. Authority vocabulary regression

Disposition: **closed**.
Mechanism: the existing test suite scans the schema, example, and
builder for the canonical reserved owner-authority token list
maintained in the runtime budget test module
(`_FORBIDDEN_AUTHORITY_TOKENS`). Adding any listed token to those
files causes a CI finding, preventing accidental authority drift in
this artifact. The token list is the single source of truth and is not
re-enumerated here so this review document remains within
authority-safe wording.
Tests:
`tests/test_pr_test_runtime_budget_observation.py::test_artifact_files_use_authority_safe_vocabulary`.

### 10. Coverage reduction smuggled in under fallback justification

Disposition: **closed**.
Mechanism: this slice extends a schema, example, manifest entry,
builder, and test module, and adds two review docs and four override
entries. It does not delete or rename any test file, any selector
entrypoint, any shard runner behavior, any required-shards
configuration, the `pr-pytest.yml` workflow, the
`core_loop_pre_pr_gate_policy.json`, or the override policy. Existing
required tests, full-suite validation on main / scheduled workflows,
and PR shard policy are unchanged.

## Residual weak seam

The fallback justification section is observation-only. Operators must
still inspect the artifact to act on a recorded broad/full-suite
fallback. There is no governed downstream consumer (APR, CLP,
dashboard) that ingests the new section yet. Wiring the fallback scope
into a downstream consumer is intentionally out of scope for this slice
and would be added in a separate downstream-consumer slice if and when
needed. The runtime budget value is still supplied via the builder's
`--runtime-budget-seconds` flag with a conservative default of `300.0`
(see EVL-RT-01 residual seam); no governed policy artifact yet records
the canonical budget value.
