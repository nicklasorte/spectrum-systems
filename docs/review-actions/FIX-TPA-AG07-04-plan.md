# FIX-TPA-AG07-04 Plan

Primary prompt type: PLAN

## Scope
- Identify contract mismatch from generated preflight diagnosis artifacts.
- Apply minimal contract-surface alignment fix for the implicated artifact(s).
- Harden TPA early contract-surface equivalence checks for changed artifacts only.
- Add SCH/GOV fail-closed checks and tests for deterministic early blocking.

## Steps
1. Read diagnosis artifacts and extract exact mismatch type, artifact_type, and disagreeing surfaces.
2. Align only the mismatched contract surfaces (manifest/schema/example/runtime) without weakening gates.
3. Extend TPA mismatch records with explicit field-surface diagnostics and trace/replay refs.
4. Add/update tests for mismatch detection, required-field gaps, stale field detection, aligned pass, and downstream block fallback.
5. Run focused test surfaces and required contract enforcement checks.
