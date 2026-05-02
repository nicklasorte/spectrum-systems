# AUTH-AUTHORING-01 - Red-Team Review

Slice: AUTH-AUTHORING-01 - Pre-Authoring Authority-Safe Language Check.

Authority scope: observation-only. The authoring check does NOT replace,
weaken, or substitute for any of:

- `scripts/run_authority_shape_preflight.py`
- `scripts/run_authority_leak_guard.py`
- `scripts/run_system_registry_guard.py`

Canonical ownership remains with the systems declared in
`docs/architecture/system_registry.md`.

This red-team review enumerates abuse patterns the new check must not
silently let through, plus shapes where the check could over- or
under-fire. Each finding is dispositioned in
`docs/review-actions/AUTH-AUTHORING-01_fix_actions.md`.

## Scope of red-team

The new surfaces under review are:

- `contracts/schemas/authority_authoring_check_record.schema.json`
- `contracts/examples/authority_authoring_check_record.example.json`
- `contracts/standards-manifest.json` (one new entry)
- `scripts/run_authority_authoring_check.py`
- `scripts/run_agent_pr_precheck.py` (one new TPA-phase observation)
- `tests/test_authority_authoring_check.py`
- `docs/governance/preflight_required_surface_test_overrides.json`
  (one new mapping line)

Existing canonical guards are out of scope - they were not modified.

## Findings

### F-1 - reserved authority terms hidden in negated phrasing
- Severity: must_fix
- Risk: an author writes "this step does not certify the run" and
  believes the negation makes the wording safe.
- Verified: `tests/test_authority_authoring_check.py
  ::test_negated_authority_term_is_flagged` confirms the negation cue
  is detected and a `negated_authority_term` finding is emitted with
  `reason_code = negated_authority_term_in_non_owner_context`.
- Disposition: addressed.

### F-2 - reserved terms in schema descriptions
- Severity: must_fix
- Risk: a non-owner schema's `description` text contains "promote" /
  "certify" / "decide" and bypasses scrutiny because the file ends in
  `.schema.json`.
- Verified: `contracts/schemas/` is in `AUTHORED_PREFIXES`; the regex
  scanner inspects raw text content, not JSON keys, so descriptions
  are scanned. The check's own schema is owner-context (in
  `SELF_OWNER_PATHS`) which is the correct exception.
- Disposition: addressed - non-owner schema descriptions are scanned
  identically to docs.

### F-3 - reserved terms in contract examples
- Severity: must_fix
- Risk: a non-owner example file embeds "promotion" / "approval"
  language that drifts into authority claims.
- Verified: `contracts/examples/` is in `AUTHORED_PREFIXES`. Owner
  example paths declared in `authority_registry.json` are skipped via
  `_load_owner_path_prefixes`.
- Disposition: addressed.

### F-4 - reserved terms in test names or comments
- Severity: must_fix
- Risk: a test in `tests/` named or commented with "promote" or
  "certify" hides authority drift behind test-only language.
- Verified: `tests/` is in `AUTHORED_PREFIXES`; both file content
  (comments, docstrings) and test names are inside the regex scope.
  `tests/test_authority_authoring_check.py` is on `SELF_OWNER_PATHS`
  because it MUST exercise the vocabulary; that exemption is narrow
  and explicit.
- Disposition: addressed.

### F-5 - protected owner acronym used in non-owner docstring
- Severity: must_fix
- Risk: a non-owner builder script's docstring says "AEX owns
  admission for this slice".
- Verified: `tests/test_authority_authoring_check.py
  ::test_protected_owner_acronym_ownership_shape_is_flagged` confirms
  the ownership-shape regex flags the acronym + verb pattern.
- Disposition: addressed.

### F-6 - generated artifact false positives
- Severity: must_fix
- Risk: a generated JSON in `outputs/` or `artifacts/` contains
  reserved values (`"decision": "noted"`) and the check fires on
  generated content the author did not write.
- Verified: `_is_generated_path` skips `outputs/`, `artifacts/`,
  `governance/reports/`, and `docs/governance-reports/` and emits
  `reason_code = generated_file_skipped`. Confirmed by
  `test_generated_artifact_path_is_skipped`.
- Disposition: addressed - default policy skips generated paths;
  authoring-time scope is preserved.

### F-7 - owner-context false positives
- Severity: must_fix
- Risk: a canonical owner file (e.g. `enforcement_engine.py`) is
  flagged for using "enforces", which is the file's legitimate
  vocabulary.
- Verified: `_load_owner_path_prefixes` reads
  `contracts/governance/authority_registry.json` and exempts both
  declared owner paths and entries in `forbidden_contexts.
  excluded_path_prefixes`. Confirmed by
  `test_canonical_owner_path_from_registry_is_skipped`.
- Disposition: addressed - owner-context wording is not flagged.

### F-8 - APR treating authoring pass as substitute for canonical guards
- Severity: must_fix (architectural)
- Risk: a future refactor folds the canonical TPA guards into the new
  authoring check, weakening the canonical authority surface.
- Verified: `tests/test_authority_authoring_check.py
  ::test_apr_runner_includes_authoring_check_when_integrated`
  asserts that, when APR integrates the authoring check, all four
  canonical TPA guard names (`tpa_authority_shape`,
  `tpa_authority_leak`, `tpa_system_registry`,
  `tpa_contract_compliance`) still appear as separate invocations in
  `scripts/run_agent_pr_precheck.py`. The integration in this slice
  adds the new check ALONGSIDE - it never replaces the canonical
  guards.
- Disposition: addressed - structural test guards against drift.

### F-9 - missing artifact treated as pass
- Severity: must_fix
- Risk: APR runs the authoring check, the subprocess crashes, no
  artifact is written, and APR mistakes silence for `pass`.
- Verified: `tpa_authority_authoring_check` in
  `scripts/run_agent_pr_precheck.py` reads the artifact's `status`
  field directly. If the file is missing or `status` cannot be
  parsed, the wrapper returns `status="block"` with reason code
  `authority_authoring_check_unknown`, which sets APR's overall
  status to `block`. Silence is never inferred as readiness.
- Disposition: addressed.

### F-10 - unknown scan state treated as pass
- Severity: must_fix
- Risk: an unreadable authored file or a changed-files resolution
  failure produces ambiguous output and is rounded up to `pass`.
- Verified: `evaluate_authoring_check` records
  `scan_unknown = True` for any unreadable file, sets
  `status = "unknown"`, and stamps `reason_code = scan_unknown`. The
  CLI's exit code (3) for `unknown` differs from `pass` (0), and the
  schema requires `reason_codes` to be non-empty when
  `status in {warn, block, unknown}`. Confirmed by
  `test_unreadable_authored_file_yields_unknown`.
- Disposition: addressed.

## Residual risks (not blocking)

- The reserved-term regex is intentionally simple: it does not
  perform semantic analysis. A determined author could split a term
  across line breaks to avoid match (e.g. `cer\ntify`). The canonical
  authority guards still scan post-merge, so this is bounded.
- The protected-owner-acronym regex uses a 60-character window,
  which can miss ownership claims spread over multiple sentences.
  Tightening the window risks under-firing; widening it risks
  noise. The canonical system_registry_guard remains authoritative.
- Owner path determination depends on
  `contracts/governance/authority_registry.json` being readable. If
  the file is missing the scanner falls back to scanning all paths;
  the canonical system_registry_guard would also fail in that case
  and would surface its own `block`.

## Confirmed non-claims

- The artifact carries `authority_scope = observation_only`.
- The schema does not include any field claiming `decision`,
  `enforcement_action`, `certified`, `promoted`, `promotion_ready`.
- The script does not write any canonical-owner artifacts and does
  not modify any owner-declared path.
- The APR integration emits a TPA-phase observation; it neither
  re-defines TPA ownership nor substitutes for any of the four
  canonical TPA guards.

## Final disposition

All `must_fix` findings are addressed in this slice; verifying tests
exist for each. No residual must_fix items. Slice is admissible
to the canonical PR-ready handoff path.
