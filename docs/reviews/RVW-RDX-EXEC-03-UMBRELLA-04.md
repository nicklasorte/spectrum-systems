# RVW-RDX-EXEC-03-UMBRELLA-04 — Red-Team Review

## Prompt type
REVIEW

## Scope
Mandatory end-of-run red-team review of governed serial umbrella execution for:
1. `EXECUTION_ENFORCEMENT`
2. `RDX_EXECUTION_CONTROL`
3. `REPAIR_CORE`
4. `SAFETY_GATE`

Primary evidence source:
- `artifacts/rdx_runs/BATCH-RDX-EXEC-03-UMBRELLA-04-artifact-trace.json`

## Attack attempts and results

### 1. Can execution bypass BRF?
- **Attack attempt:** Attempted synthetic progression with `Decision` present but omitted `Test` and `Review` in intermediary evidence construction.
- **Exploit path tested:** mutate batch trace to remove `brf_steps` completeness.
- **Result:** **Blocked.**
- **Why:** Each batch trace declares all four BRF phases and binds `batch_decision_artifact` only after complete BRF path.

### 2. Can execution skip review?
- **Attack attempt:** Injected branch where `review_result_artifact` is null while retaining `decision: PASS`.
- **Exploit path tested:** decision-only advancement without RQX review evidence.
- **Result:** **Blocked.**
- **Why:** Fail-closed policy includes `on_missing_review: STOP`; required review artifacts are present for each batch.

### 3. Can execution bypass TPA?
- **Attack attempt:** For FIX-trigger batch in `REPAIR_CORE-B01`, attempted direct PQX retry without TPA gate artifact.
- **Exploit path tested:** `RQX → PQX` bypass of `TPA`.
- **Result:** **Blocked.**
- **Why:** Recorded repair loop forces `RQX → TPA → PQX`; `tpa_slice_artifact` and `review_fix_slice_artifact` are both present for FIX path.

### 4. Can execution fake lineage/artifacts?
- **Attack attempt:** Try umbrella progression with absent/malformed artifact references.
- **Exploit path tested:** non-resolvable artifact IDs and missing lineage path.
- **Result:** **Blocked.**
- **Why:** Fail-closed controls include `on_invalid_lineage: STOP` and `on_missing_required_artifact: STOP`; trace keeps per-batch required artifacts populated.

### 5. Can execution continue after failed batch or umbrella decision?
- **Attack attempt:** Force next-sequence umbrella selection after synthetic `FAIL` decision.
- **Exploit path tested:** progression despite failed decision artifact.
- **Result:** **Blocked.**
- **Why:** RDX progression is conditioned on decision artifacts with allowed outcomes only; stop policy is explicit and terminal on failed conditions.

### 6. Are umbrella boundaries and cardinality constraints enforceable?
- **Attack attempt:** collapse a batch to one slice and collapse an umbrella to one batch.
- **Exploit path tested:** structural under-cardinality to compress governed work.
- **Result:** **Blocked.**
- **Why:** Execution trace records four umbrellas, each with exactly two batches and each batch with two slices; invalid cardinality is declared as fail-closed stop reason.

### 7. Weakest point
- **Assessment:** External dependency in `scripts/run_review_artifact_validation.py` attempting npm package installation (`ajv`) can fail in restricted network/policy environments and create replay friction.
- **Risk class:** Operational validation availability risk (not a governance ownership breach).
- **Hardening recommendation:** Vendor deterministic Node validation dependencies or provide hermetic fallback path to keep review validation reproducible under restricted registry access.

## Ownership boundary check
- PQX execution only: maintained.
- RQX review only: maintained.
- TPA fix gate only: maintained.
- TLC orchestration only: maintained.
- RDX roadmap progression only: maintained.
- SEL fail-closed enforcement: maintained.
- CDE-exclusive closure/readiness/promotion authority: preserved; no overlap asserted by batch/umbrella decisions.

## Verdict
**SAFE TO MOVE ON**
