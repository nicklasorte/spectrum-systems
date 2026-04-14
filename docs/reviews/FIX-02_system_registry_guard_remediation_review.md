# FIX-02 System Registry Guard Remediation Review

## Failure Observed
The SRG command over the BXT-01 changed surface returned:
- `DIRECT_OWNERSHIP_OVERLAP`
- `NEW_SYSTEM_MISSING_REGISTRATION`
- `PROTECTED_AUTHORITY_VIOLATION`
- `SHADOW_OWNERSHIP_OVERLAP`

## Root Cause By Reason Code
- `NEW_SYSTEM_MISSING_REGISTRATION`: false-positive acronym capture (`STR`) from Python type annotation text (`acronym: str`) due case-insensitive acronym regex.
- `DIRECT_OWNERSHIP_OVERLAP` and `SHADOW_OWNERSHIP_OVERLAP`: false positives from non-authoritative metadata text in `contracts/standards-manifest.json` notes fields.
- `PROTECTED_AUTHORITY_VIOLATION`: false positives from scanning non-authoritative test fixtures and descriptive notes as if they were owner claims.

## Exact Offending Paths/Symbols
- `spectrum_systems/modules/governance/system_registry_guard.py` line around `acronym: str` detected as fake acronym `STR`.
- `contracts/standards-manifest.json` descriptive notes containing tokens like `FRE`, `execution`, `authority`.
- `tests/test_system_registry_guard.py` fixture acronyms (`OLD`, `REM`, `ZZZ`) used for negative test scenarios.

## Ownership Resolution Applied
- Classified test fixtures, review artifacts, and standards-manifest metadata as non-authoritative ownership surfaces via guard policy (`non_authority_path_prefixes`, `non_authority_exact_paths`).
- Tightened owner-like symbol scanning to authoritative surface suffixes only.
- Kept strict owner overlap/protected authority checks active on authoritative surfaces.

## Code Changes Made
1. Extended SRG policy with:
   - `non_authority_path_prefixes`
   - `non_authority_exact_paths`
   - `authoritative_owner_scan_suffixes`
2. Hardened SRG parser/evaluator:
   - removed case-insensitive acronym regex to stop `str`→`STR` false positives,
   - added authoritative/non-authority path classification,
   - added structured diagnostics with `resolution_category`,
   - deduplicated diagnostics while preserving reason codes.
3. Added targeted tests for:
   - non-authority standards-manifest allowance,
   - real FIX-02 changed-surface pass outcome,
   - diagnostic resolution-category presence.

## Guard Hardening Added
- Owner-like symbol precheck now runs only on authoritative surfaces and skips non-authority files by policy.
- Protected authority and overlap checks remain fail-closed where owner-claim language appears on authoritative paths.
- Diagnostics now include explicit remediation routing (`register`, `fold_into_owner`, `convert_to_non_authority_artifact`, `remove`).

## Tests Added or Changed
- Updated `tests/test_system_registry_guard.py` with:
  - non-authority metadata allowance test,
  - FIX-02 changed-surface pass test,
  - diagnostics resolution-category assertion on protected authority violation.

## Remaining Registry Risks
- Non-authority path policy must stay curated; accidental placement of owner-claim language in authoritative paths still blocks (desired).
- Future net-new owner systems still require same-change canonical registration in `docs/architecture/system_registry.md`.

## Validation Commands Run
- `python scripts/run_system_registry_guard.py --base-ref c99434a9ef9b4b7e04b3fb88b11282c37a5dc71a --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json`
- `pytest tests/test_system_registry_guard.py -q`
- `pytest tests/test_three_letter_system_enforcement.py -q`
- `pytest tests/test_system_registry.py -q`
- `pytest tests/test_system_registry_boundaries.py -q`
- `pytest tests/test_system_registry_boundary_enforcement.py -q`

## Final Verdict
- Current FIX-02 failing SRG scenario now passes for the correct reason (authoritative owner checks preserved; non-authority metadata no longer treated as ownership).
- Recurrence prevention is now policy-backed, test-backed, and diagnostic-rich.
