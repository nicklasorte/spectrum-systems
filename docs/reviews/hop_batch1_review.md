# HOP-BATCH-1 Red Team Review

## Prompt type
REVIEW

## Scope
- malformed artifacts
- missing evals
- schema violations
- eval tampering
- trace gaps

## Findings

1. **Malformed artifact acceptance risk**
   - **Severity:** High
   - **Observation:** Append path must reject artifacts missing required envelope fields.
   - **Required fix:** Enforce schema validation before append and hard-fail writes.
   - **Status:** Fixed via `ExperienceStore.append()` contract validation.

2. **Missing eval dataset gate risk**
   - **Severity:** Critical
   - **Observation:** Evaluator could run with empty eval cases and emit misleading score.
   - **Required fix:** Block when eval set is empty or tampered.
   - **Status:** Fixed via `HOPEvaluationError` on empty case set and safety checks.

3. **Candidate interface bypass risk**
   - **Severity:** High
   - **Observation:** Candidate import/method mismatch can leak into eval.
   - **Required fix:** Pre-eval validator must enforce required methods and emit failure artifact.
   - **Status:** Fixed in `validate_candidate()`.

4. **Trace completeness gap risk**
   - **Severity:** High
   - **Observation:** Trace-less artifacts undermine replay and observability.
   - **Required fix:** Schema-level required `trace` and reject store writes without trace.
   - **Status:** Fixed by HOP schemas + failure tests.

5. **Eval leakage / tamper risk**
   - **Severity:** Critical
   - **Observation:** Hardcoded eval identifiers or bypass flags can game evaluation.
   - **Required fix:** Safety checks must block and emit failure artifact.
   - **Status:** Fixed in `run_safety_checks()` with explicit leakage/tamper detection.

## Required fixes implemented
- Added strict Draft 2020-12 schemas for all HOP artifacts.
- Added validator, evaluator fail-closed checks, and safety checks.
- Added append-only validated store and query surfaces.
- Added integration/failure tests for every critical finding.

## Residual risk
- Heuristic leakage detection can produce false positives/false negatives; deeper static/code provenance checks are deferred to BATCH-2.
