## SF-14 Workflow / Exit-Code Review

### Overall Decision
FAIL

### Scope Reviewed
- `scripts/run_release_canary.py` (expected by SF-14 scope)
- Exit-code behavior for release decision plumbing
- Emitted artifacts/output path expectations for release decision evidence
- Workflow/CI wiring relevant to SF-14 release+canary execution
- Promote/hold/rollback surfacing to automation

### Evidence Snapshot
- `scripts/run_release_canary.py` is not present in the repository.
- No workflow file invokes `run_release_canary.py`.
- No workflow file references `evaluation_release_record`.
- No workflow file contains `continue-on-error` masking for this path because no SF-14 release+canary path is wired at all.

### Critical Operational Risks
- [ ] **No enforceable release decision gate exists for SF-14.** There is no `scripts/run_release_canary.py` entrypoint and no workflow wiring that would consume its exit codes.
- [ ] **No machine-consumable release evidence contract is wired.** `evaluation_release_record` is not emitted by an SF-14 workflow path, so downstream automation cannot prove promote/hold/rollback decisions.

### High-Risk Gaps
- Exit-code semantics `0=promote`, `1=hold`, `2=rollback` are not enforceable because no SF-14 runner exists to produce them.
- Fail-closed semantics for policy-load failure, comparison execution failure, or artifact-write failure are unverifiable in CI because no SF-14 job executes.
- There is no deterministic output path/name contract for release decision artifacts in a release+canary workflow, which blocks reliable downstream artifact collection.

### Confirmed Safeguards
- Existing workflows do not use `continue-on-error` for current jobs, reducing accidental masking where gates do exist.
- Current lifecycle workflow uploads CI gate artifacts with `if: always()`, which is useful for debugging in other enforcement paths.

### Recommended Fixes (ordered)
1. Add `scripts/run_release_canary.py` with strict, mutually-exclusive exit codes:
   - `0` only on promote
   - `1` only on hold
   - `2` only on rollback
   - all operational exceptions return non-zero and never map to promote
2. Ensure `evaluation_release_record` is written for all non-crash outcomes (promote/hold/rollback/error) before process exit; include deterministic fields needed for automation and debugging.
3. Add a dedicated `.github/workflows/*` SF-14 release+canary job that directly executes `run_release_canary.py` and fails the workflow on non-zero exits.
4. Persist release decision artifacts under deterministic repo-native paths (for example `outputs/release_canary/<run_id>/evaluation_release_record.json`) and upload them unconditionally via artifact upload.
5. Add explicit tests for fail-closed behavior: policy-load error, comparison exception, and artifact-write failure must not produce promote exit semantics.

### Residual Risk
- Until SF-14 runner + workflow wiring are implemented, release decisions remain operationally unenforced by automation and are therefore bypassable by omission.
