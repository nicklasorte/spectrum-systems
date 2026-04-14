# Plan — FIX-02 system registry guard remediation

## Prompt type
PLAN

## Failure reason codes observed
- DIRECT_OWNERSHIP_OVERLAP
- NEW_SYSTEM_MISSING_REGISTRATION
- PROTECTED_AUTHORITY_VIOLATION
- SHADOW_OWNERSHIP_OVERLAP

## Suspected triggers (path/symbol)
1. `contracts/standards-manifest.json` notes text (e.g., `FRE ... execution authority`) is being interpreted as owner claims.
2. `tests/test_system_registry_guard.py` fixture acronyms (`OLD`, `REM`, `ZZZ`) are being treated as real ownership surfaces.
3. `spectrum_systems/modules/governance/system_registry_guard.py` dataclass type annotation (`acronym: str`) is matched as fake acronym `STR`.
4. Broad owner-claim regex over JSON content causes protected-authority and overlap false positives.

## Trigger classification
- `standards-manifest` findings: non-authoritative artifact metadata (should be treated as report/description text, not ownership claim).
- `tests/*` fixture findings: test-only synthetic data (non-authoritative validator fixtures).
- `str` detection in code: parser bug, invalid owner-like token detection.
- No evidence of a true net-new owner in the changed set.

## Intended remediation
1. Add explicit non-authority path policy for metadata/test/report surfaces.
2. Harden acronym/owner detection to avoid lowercase type annotations and JSON note text false positives.
3. Add owner-like symbol precheck that only scans authoritative ownership surfaces and emits precise diagnostics.
4. Add structured resolution categories to guard findings (`register`, `fold_into_owner`, `convert_to_non_authority_artifact`, `remove`).
5. Add focused tests for:
   - failing scenario now passing
   - unregistered owner-like surface fail
   - protected authority leak fail
   - shadow overlap fail
   - valid non-authority artifacts allowed

## Planned file changes
- `contracts/governance/system_registry_guard_policy.json`
- `spectrum_systems/modules/governance/system_registry_guard.py`
- `tests/test_system_registry_guard.py`
- `docs/reviews/FIX-02_system_registry_guard_remediation_review.md`

## Recurrence prevention
- Non-authority mode/path registry in policy.
- Early owner-like precheck restricted to authoritative surfaces.
- More actionable diagnostics with offending symbol/path and resolution category.
