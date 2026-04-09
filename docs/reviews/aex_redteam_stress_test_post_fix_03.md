# AEX Red-Team Stress Test (Post FIX-03) — 2026-04-09

## 1. Executive Verdict
- Boundary status: **still soft at artifact authenticity seam**.
- Can bypass happen today: **YES**.
- Verdict: **BLOCKER present**. The invariant is not universal because repo-write PQX execution can still be admitted through forged lineage artifacts that satisfy schema + cross-field checks without proving AEX/TLC provenance.

## 2. Verification of Previous Fixes
- execution_ready bypass: **closed** at cycle runner path. `execution_ready` now routes through `handoff_to_pqx`, which enforces repo-write lineage before `run_pqx_slice`. Evidence: `cycle_runner` execution branch + adapter lineage gate.
- fix_roadmap_ready bypass: **closed** at cycle runner fix re-entry path. Fix bundle re-entry also routes through `handoff_to_pqx` and fails closed when lineage is missing.
- direct caller / run_pqx_slice loophole: **partially closed, not fully closed**.
  - Closed for `unknown`/missing intent at the PQX execution edge (`run_pqx_slice` blocks unless explicit `execution_intent` is `repo_write` or `non_repo_write`).
  - Not closed for forged lineage: repo-write execution can pass with syntactically/relationally valid but non-authentic artifacts.
- evidence:
  - PQX boundary guard enforces intent + lineage presence/shape + continuity checks.
  - Structural tests enforce direct-caller allowlist and `execution_intent` keyword presence.
  - No authenticity primitive (signature/issuer binding/attestation nonce) is required by guard or schemas.

## 3. Highest-Risk Failure Paths

### Path 1 — Forged lineage accepted at PQX execution edge
- severity: **BLOCKER**
- files:
  - `spectrum_systems/modules/runtime/repo_write_lineage_guard.py`
  - `spectrum_systems/modules/runtime/pqx_slice_runner.py`
  - `scripts/pqx_runner.py`
- exact scenario:
  1. Caller invokes `scripts/pqx_runner.py` with `--execution-intent repo_write` and points lineage paths to locally fabricated JSON artifacts.
  2. Fabricated artifacts satisfy schema and internal ref consistency (`request_id`, `trace_id`, refs).
  3. `validate_repo_write_lineage` accepts them because it checks structure/continuity but does not verify artifact provenance authenticity.
  4. `run_pqx_slice` proceeds as repo-write.
  5. AEX is bypassed in practice because lineage is self-issued.

### Path 2 — Intent honesty dependency on direct callers
- severity: **HIGH**
- files:
  - `spectrum_systems/modules/runtime/pqx_slice_runner.py`
  - `scripts/pqx_runner.py`
  - `spectrum_systems/modules/runtime/codex_to_pqx_task_wrapper.py`
  - `spectrum_systems/modules/pqx_backbone.py`
  - `spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py`
  - `spectrum_systems/modules/runtime/pqx_sequence_runner.py`
- exact scenario:
  1. Boundary relies on caller-provided `execution_intent`.
  2. If a future caller mislabels a mutating request as `non_repo_write`, PQX lineage gate does not run.
  3. Current structural test reduces this risk by forcing explicit intent declaration, but semantic correctness of declared intent is not enforced at runtime.

### Path 3 — Role-drift via duplicated intent inference logic
- severity: **MEDIUM**
- files:
  - `spectrum_systems/modules/runtime/top_level_conductor.py`
  - `spectrum_systems/orchestration/pqx_handoff_adapter.py`
  - `spectrum_systems/aex/engine.py`
- exact scenario:
  1. Multiple layers infer repo mutation intent with subtly different precedence rules.
  2. Future edits can desynchronize interpretation (e.g., boolean flag vs admission execution type precedence).
  3. Desync risk creates latent fail-open or false-block behavior under churn.

## 4. Fail-Closed Assessment
- **Strong points**:
  - `run_pqx_slice` blocks unknown/missing `execution_intent` (`REPO_WRITE_LINEAGE_REQUIRED`).
  - Repo-write path blocks on missing/invalid lineage artifacts.
  - `handoff_to_pqx` rejects unknown mutation intent and rejects repo-write requests without lineage.
  - TLC refuses repo-write progression without admission lineage and constructs `tlc_handoff_record` for admitted paths.
- **Residual fail-open seam**:
  - Fail-closed is only as strong as authenticity of supplied artifacts. Current enforcement is fail-closed on *shape/consistency*, not on *issuer authenticity*.

## 5. Role-Boundary Assessment
- AEX still owns admission classification/rejection semantics.
- TLC still orchestrates and emits handoff artifact.
- PQX now correctly enforces execution-edge lineage.
- **Role-collapse risk**: moderate duplication of admission-adjacent intent checks across AEX/TLC/adapter/PQX. Not a present exploit, but drift-prone.

## 6. Trace / Lineage Assessment
- Trace continuity checks are good (`trace_id`, `request_id`, normalized ref, handoff refs).
- TLC handoff artifact makes path reconstructable across AEX→TLC→PQX.
- **Critical weakness**: continuity is not equivalent to authenticity. A coherent forged chain currently passes.

## 7. Schema / Contract Assessment
- Schemas constrain shape and required fields well (`additionalProperties: false`, required refs).
- Runtime requires stricter semantics than schema alone (accepted status + repo_write type + ref continuity).
- **Mismatch seam**: contracts do not encode authenticity/provenance guarantees beyond free-form `produced_by` strings.

## 8. Test Coverage Assessment
- Strong coverage exists for:
  - unknown intent fail-closed at PQX edge,
  - missing lineage rejection,
  - TLC admission requirement,
  - cycle runner execution_ready and fix_roadmap_ready re-entry hardening,
  - direct caller allowlist + intent declaration structural checks.
- Gap:
  - No test proves rejection of syntactically valid but forged lineage artifacts from non-AEX issuers.
  - No test enforces cryptographic/attested provenance because mechanism does not exist.

## 9. Drift Forecast
- Most plausible future bypass: a new direct caller sets `execution_intent="non_repo_write"` for a mutating flow (semantic lie), passing structural signature requirements while bypassing lineage checks.
- First seam likely to rot: duplicated intent inference logic precedence across layers.
- Convention-dependent invariant: issuer authenticity (`produced_by`) and caller truthfulness on mutation intent.

## 10. Required Fixes
Single surgical fix batch (highest leverage):

1. Introduce **lineage authenticity binding** at PQX boundary.
   - Add a required, verifiable provenance field across `build_admission_record`, `normalized_execution_request`, and `tlc_handoff_record` (e.g., signed digest/attestation token over stable canonical payload + issuer key ID).
   - Validate this attestation inside `validate_repo_write_lineage` before accepting repo-write execution.
   - Add a regression test that fabricates internally consistent artifacts with invalid/missing attestation and proves PQX blocks.

## 11. Final Recommendation
**DO NOT MOVE ON**

Rationale:
- Required questions answered explicitly:
  1. Is AEX now the ONLY enforceable repo-write ingress in practice? **No. Forged lineage can emulate AEX/TLC outputs and pass PQX checks.**
  2. Does the PQX execution-boundary guard fully close the previously identified direct-caller loophole? **Partially; it closes missing/unknown intent and missing lineage, but not forged lineage authenticity bypass.**
  3. Are execution_ready and fix_roadmap_ready both still closed after FIX-03? **Yes, on the cycle_runner path.**
  4. What is the most plausible remaining bypass today? **Submit coherent forged lineage artifacts via direct caller/CLI.**
  5. Which guard is strongest? **PQX execution-edge unknown-intent + required-lineage gate in `run_pqx_slice`.**
  6. Which guard is weakest? **Lineage authenticity (currently unproven; `produced_by` is non-authoritative).**
  7. What invariant still depends on convention? **“Lineage artifacts are truly AEX/TLC-issued” and “execution_intent labels are truthful.”**
  8. If one test were removed, what failure becomes most likely? **Remove direct-caller structural intent declaration test; a new/changed caller can silently omit explicit intent semantics and reintroduce boundary ambiguity.**
  9. Is AEX now “done for now”? **No. One authenticity fix batch is still required.**
