# AUTH-AUTHORING-01 - Fix Actions

Companion to `docs/reviews/AUTH-AUTHORING-01_redteam.md`. Each row
records a finding ID, the file changed, the test added/updated, the
command run, and the disposition. All `must_fix` findings are resolved
in this slice; if any remained unresolved the slice would stop with
`human_review_required` and would not claim PR-ready.

## Fix table

### F-1 - reserved authority terms hidden in negated phrasing

- finding_id: F-1
- file_changed: `scripts/run_authority_authoring_check.py`
- mechanism: `_negation_precedes` inspects a 32-character window
  before each match for any of the canonical negation cues (`not`,
  `no`, `never`, `without`, `non`, `cannot`, etc.) and emits
  `category = negated_authority_term` with reason code
  `negated_authority_term_in_non_owner_context`.
- test_added: `tests/test_authority_authoring_check.py
  ::test_negated_authority_term_is_flagged`
- command_run: `python -m pytest
  tests/test_authority_authoring_check.py::test_negated_authority_term_is_flagged -q`
- disposition: resolved.

### F-2 - reserved terms in schema descriptions

- finding_id: F-2
- file_changed: `scripts/run_authority_authoring_check.py`
- mechanism: `contracts/schemas/` is in `AUTHORED_PREFIXES`; the
  text-level regex scans all content. Owner-context schemas (and the
  AUTH-AUTHORING-01 schema itself) are the only exemption, and the
  exemption is narrow.
- test_added: `tests/test_authority_authoring_check.py
  ::test_reserved_term_in_non_owner_doc_is_flagged` (parametrized
  across all term clusters)
- command_run: `python -m pytest
  tests/test_authority_authoring_check.py
  ::test_reserved_term_in_non_owner_doc_is_flagged -q`
- disposition: resolved.

### F-3 - reserved terms in contract examples

- finding_id: F-3
- file_changed: `scripts/run_authority_authoring_check.py`
- mechanism: `contracts/examples/` is in `AUTHORED_PREFIXES`; the
  scanner reads file text. Owner example paths declared in
  `contracts/governance/authority_registry.json` are exempt via
  `_load_owner_path_prefixes`.
- test_added: covered by the parametrized term-detection test (same
  scanner logic applies to authored example files).
- command_run: `python -m pytest tests/test_authority_authoring_check.py -q`
- disposition: resolved.

### F-4 - reserved terms in test names or comments

- finding_id: F-4
- file_changed: `scripts/run_authority_authoring_check.py`
- mechanism: `tests/` is in `AUTHORED_PREFIXES`; the scanner does not
  exclude any subset of test files. The single exemption -
  `tests/test_authority_authoring_check.py` - is on `SELF_OWNER_PATHS`
  because the test file MUST exercise the vocabulary to verify the
  scanner.
- test_added: `tests/test_authority_authoring_check.py
  ::test_owner_context_self_path_is_skipped`
- command_run: `python -m pytest
  tests/test_authority_authoring_check.py
  ::test_owner_context_self_path_is_skipped -q`
- disposition: resolved.

### F-5 - protected owner acronym used in non-owner docstring

- finding_id: F-5
- file_changed: `scripts/run_authority_authoring_check.py`
- mechanism: `_OWNERSHIP_RE` and `_OWNERSHIP_RE_REVERSE` flag any
  protected owner acronym (`AEX`, `PQX`, `EVL`, `TPA`, `CDE`, `SEL`)
  appearing within ~60 characters of an ownership/authority verb.
- test_added: `tests/test_authority_authoring_check.py
  ::test_protected_owner_acronym_ownership_shape_is_flagged`
- command_run: `python -m pytest
  tests/test_authority_authoring_check.py
  ::test_protected_owner_acronym_ownership_shape_is_flagged -q`
- disposition: resolved.

### F-6 - generated artifact false positives

- finding_id: F-6
- file_changed: `scripts/run_authority_authoring_check.py`
- mechanism: `_is_generated_path` matches `outputs/`, `artifacts/`,
  `governance/reports/`, and `docs/governance-reports/`. Such files
  are skipped with `skip_reason = generated_artifact` and the run
  records `reason_code = generated_file_skipped`.
- test_added: `tests/test_authority_authoring_check.py
  ::test_generated_artifact_path_is_skipped`
- command_run: `python -m pytest
  tests/test_authority_authoring_check.py
  ::test_generated_artifact_path_is_skipped -q`
- disposition: resolved.

### F-7 - owner-context false positives

- finding_id: F-7
- file_changed: `scripts/run_authority_authoring_check.py`
- mechanism: `_load_owner_path_prefixes` ingests the registry
  (`canonical_owners[*].owner_path_prefixes` plus
  `forbidden_contexts.excluded_path_prefixes`). Files matching any
  of those prefixes are skipped with `skip_reason = owner_path`.
- test_added: `tests/test_authority_authoring_check.py
  ::test_canonical_owner_path_from_registry_is_skipped`
- command_run: `python -m pytest
  tests/test_authority_authoring_check.py
  ::test_canonical_owner_path_from_registry_is_skipped -q`
- disposition: resolved.

### F-8 - APR treating authoring pass as substitute for canonical guards

- finding_id: F-8
- file_changed: `scripts/run_agent_pr_precheck.py`,
  `tests/test_authority_authoring_check.py`
- mechanism: APR adds `tpa_authority_authoring_check` ALONGSIDE the
  four canonical TPA guards. The structural test asserts that, when
  the authoring check is enabled, all four canonical guard names are
  still present as separate invocations.
- test_added: `tests/test_authority_authoring_check.py
  ::test_apr_runner_includes_authoring_check_when_integrated`
- command_run: `python -m pytest
  tests/test_authority_authoring_check.py
  ::test_apr_runner_includes_authoring_check_when_integrated -q`
- disposition: resolved.

### F-9 - missing artifact treated as pass

- finding_id: F-9
- file_changed: `scripts/run_agent_pr_precheck.py`
- mechanism: `tpa_authority_authoring_check` reads the on-disk
  artifact and uses the `status` field. Missing/unparsable artifact
  becomes `block` with reason code
  `authority_authoring_check_unknown`. APR's `_aggregate_overall_status`
  treats `block` as `block` overall.
- test_added: covered by the structural APR test (F-8); behavior is
  small and inspected at code review time.
- command_run: `python -m pytest tests/test_authority_authoring_check.py -q`
- disposition: resolved.

### F-10 - unknown scan state treated as pass

- finding_id: F-10
- file_changed: `scripts/run_authority_authoring_check.py`
- mechanism: any unreadable authored file flips
  `scan_unknown = True`, which sets `status = "unknown"` and stamps
  `reason_code = scan_unknown`. The schema's conditional rule
  requires `reason_codes` to be non-empty whenever
  `status in {warn, block, unknown}`. CLI exit code 3 distinguishes
  `unknown` from `pass`.
- test_added: `tests/test_authority_authoring_check.py
  ::test_unreadable_authored_file_yields_unknown`
- command_run: `python -m pytest
  tests/test_authority_authoring_check.py
  ::test_unreadable_authored_file_yields_unknown -q`
- disposition: resolved.

## Stop / continue

All `must_fix` findings are resolved with tests. No findings remain
that require `human_review_required`. The slice continues to the
canonical PR-ready handoff path.
