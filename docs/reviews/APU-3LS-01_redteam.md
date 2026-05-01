# APU-3LS-01 red-team review

## must_fix
- MF-01: Missing CLP or AGL evidence could be treated as clean update readiness. Resolved by fail-closed not_ready logic and reason codes.
- MF-02: Claimed present leg without artifact refs could be accepted. Resolved by downgrade to partial and readiness block.
- MF-03: CLP warn with non-allowed reason code could be treated as clean. Resolved via policy allowlist checks.
- MF-04: Unknown repo_mutating could drift to ready path. Resolved via explicit not_ready default.

## should_fix
- SF-01: Expand fixture coverage for PR prose substitution rejection in CLI-level tests.

## observation
- OBS-01: Current AGL inputs vary by producer format; policy supports leg out-of-scope markers to keep observation surface explicit.
