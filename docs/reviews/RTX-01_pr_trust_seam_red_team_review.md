# RTX-01 — PR trust seam red team review

## 1) Scope reviewed

Reviewed the live PR trust seam surfaces exactly in requested scope:

- `.github/workflows/artifact-boundary.yml`
- `.github/workflows/pr-autofix-contract-preflight.yml`
- `scripts/run_contract_preflight.py`
- `scripts/run_pytest_trust_gap_audit.py`
- `spectrum_systems/modules/runtime/pytest_selection_integrity.py`
- `spectrum_systems/modules/runtime/preflight_failure_normalizer.py`
- `spectrum_systems/modules/runtime/github_pr_autofix_contract_preflight.py`
- Contract schemas/examples/tests for:
  - `contract_preflight_result_artifact`
  - `pytest_execution_record`
  - `pytest_selection_integrity_result`
  - `pytest_trust_gap_audit_result`

Also cross-checked test coverage for the seam logic in:

- `tests/test_artifact_boundary_workflow_pytest_enforcement.py`
- `tests/test_contract_preflight.py`
- `tests/test_pytest_selection_integrity.py`
- `tests/test_preflight_failure_normalizer.py`
- `tests/test_pytest_trust_gap_audit.py`

---

## 2) Trust seam traced

Authoritative path traced as implemented:

1. `artifact-boundary` workflow resolves refs and runs `scripts/run_contract_preflight.py`.
2. If preflight non-zero and auto-repair eligible, workflow invokes `scripts/run_github_pr_autofix_contract_preflight.py`.
3. Workflow-side Python trust checks then require, for PR ALLOW/WARN outcomes:
   - non-empty `pytest_execution_record_ref`
   - execution record file exists
   - `executed=true`
   - non-empty `selected_targets`
   - non-empty `pytest_selection_integrity_result_ref`
   - selection artifact exists and decision is `ALLOW`
4. The preflight script itself emits and validates:
   - `pytest_execution_record.json`
   - `pytest_selection_integrity_result.json`
   - `contract_preflight_result_artifact.json`
5. Autofix workflow independently re-enforces similar trust checks after rerun.

Overall: this is materially stronger than prior bypassable variants (especially removal of early-success bypass and explicit PR invariants), but still leaves exploitable trust gaps below.

---

## 3) Top 5 vulnerabilities or residual risks

### Finding 1 — **Proven vulnerability**: workflow accepts untrusted artifact refs without boundary binding

- **Category:** stale/fabricated artifact acceptance; artifact reuse across runs
- **Severity:** **High**
- **Exploit sketch:**
  1. Modify preflight-producing code path (or any upstream artifact writer) to set `pytest_execution_record_ref` and `pytest_selection_integrity_result_ref` to attacker-controlled JSON files committed in-repo (or stale files in workspace path).
  2. Ensure those JSON files satisfy minimal expected fields (`executed=true`, non-empty `selected_targets`, `selection_integrity_decision=ALLOW`).
  3. Workflow trust step reads those refs verbatim and accepts them.
- **Why currently allowed / nearly allowed:**
  - Workflow only checks that the referenced path exists and contains permissive fields.
  - It does **not** constrain refs to `outputs/contract_preflight/`, does not require same-run provenance token, and does not bind artifacts to `github.sha`.
  - Schemas do not include immutable run/commit binding for execution/selection artifacts.
- **Recommended fix:**
  - Hard fail unless refs are exactly expected canonical paths under `outputs/contract_preflight/`.
  - Add and enforce `source_commit_sha`, `workflow_run_id`, `workflow_job`, and deterministic hash linkage from result artifact → execution/selection artifacts.
- **Mandatory before more roadmap work?** **Yes (mandatory).**

### Finding 2 — **Plausible seam weakness**: PR `WARN` outcomes are treated as trusting pass

- **Category:** workflow branching bypass / warning path that should be block
- **Severity:** **High**
- **Exploit sketch:**
  1. Force degraded detection mode (e.g., ref-resolution breakage, shallow history edge) while preserving otherwise “passed” status.
  2. `map_preflight_control_signal` can emit `WARN` for `status == passed and degraded`.
  3. Both workflows accept `ALLOW` **or `WARN`** as pass-equivalent in trust checks.
- **Why currently allowed / nearly allowed:**
  - Workflow checks gate on `decision in {"ALLOW", "WARN"}`.
  - `WARN` explicitly exists for degraded detection, which is exactly where trust confidence is reduced.
- **Recommended fix:**
  - For PR seam: treat `WARN` as non-passing (`BLOCK`) unless explicitly approved via separate human-governed override artifact.
- **Mandatory before more roadmap work?** **Yes (mandatory).**

### Finding 3 — **Plausible seam weakness**: changed-path fallback narrows to `contracts/` during ref failures

- **Category:** missing mapping drift; partial enforcement CI semantics divergence
- **Severity:** **Medium-High**
- **Exploit sketch:**
  1. Cause base/head diff resolution to fail.
  2. Fallback logic inspects local changes but keeps only `contracts/` paths in several fallback branches.
  3. Non-contract changes (e.g., `scripts/`, runtime modules, workflow files) can be dropped from impact classification.
  4. Required-target derivation can become incomplete; fallback suite may still satisfy minimum threshold.
- **Why currently allowed / nearly allowed:**
  - `_local_workspace_changes` and `working_tree_vs_HEAD` fallback filters to `contracts/` only.
  - Degraded path can proceed to full governed contract scan that does not include scripts/runtime/workflow surfaces.
- **Recommended fix:**
  - In degraded/ref-failure mode, fail closed for PR unless complete governed surface diff includes `contracts/`, `scripts/`, `spectrum_systems/`, `.github/workflows/`, and policy docs.
  - Add explicit invariant: PR with degraded non-exhaustive path resolution cannot ALLOW/WARN.
- **Mandatory before more roadmap work?** **Yes (mandatory).**

### Finding 4 — **Governance drift risk**: selection-integrity policy coverage is sparse vs governed prefixes

- **Category:** policy/config loophole; missing mapping drift
- **Severity:** **Medium**
- **Exploit sketch:**
  1. Change a governed path covered by prefix (e.g., `.github/workflows/` or many runtime files) not represented in `surface_rules`.
  2. Effective required targets can remain empty or under-constrained.
  3. Meeting minimum threshold of 1 selected target can produce ALLOW despite insufficient semantic coverage.
- **Why currently allowed / nearly allowed:**
  - Policy `governed_surface_prefixes` is broad, but `surface_rules` presently only define a few concrete mappings.
  - Threshold-only path can pass when specific required targets are absent.
- **Recommended fix:**
  - Add fail-closed policy check: if changed path matches governed prefix and has no explicit mapping rule, selection integrity must BLOCK.
  - Add CI test to assert mapping completeness for all governed prefixes used by trust seam files.
- **Mandatory before more roadmap work?** **No, but strongly recommended before next enforcement expansion.**

### Finding 5 — **Governance drift risk**: workflow tests are mostly string-presence checks, not execution-semantics tests

- **Category:** workflow branching bypass via untested semantics drift
- **Severity:** **Medium-Low**
- **Exploit sketch:**
  1. Refactor workflow shell/Python logic while preserving key strings.
  2. Existing tests pass because they assert text presence/absence only.
  3. Runtime behavior can still drift into false-green paths (ordering, conditional boundaries, error handling).
- **Why currently allowed / nearly allowed:**
  - `tests/test_artifact_boundary_workflow_pytest_enforcement.py` validates string tokens, not end-to-end behavior against crafted artifacts.
- **Recommended fix:**
  - Add execution-level tests (local harness or action-simulator style) that run the gate script snippets against synthetic artifact sets: valid ALLOW, forged ref, stale ref, WARN+degraded, empty selection, blocked integrity, etc.
- **Mandatory before more roadmap work?** **No (recommended).**

---

## 4) Severity ranking

1. **High (mandatory):** Untrusted artifact refs accepted without run/commit binding.  
2. **High (mandatory):** `WARN` treated as pass-equivalent in PR trust seam.  
3. **Medium-High (mandatory):** Ref-failure changed-path fallback drops non-contract governed surfaces.  
4. **Medium (recommended):** Sparse selection-integrity mappings vs governed prefixes.  
5. **Medium-Low (recommended):** Workflow tests assert strings, not executable seam semantics.

---

## 5) Exploit sketch for each

(Consolidated above under each finding; no additional exploit path omitted.)

---

## 6) Why current implementation allows or nearly allows each

(Consolidated above under each finding; explicitly separated into “proven vulnerability”, “plausible seam weakness”, and “governance drift risk”.)

---

## 7) Recommended fix

Priority hardening set:

1. **Artifact provenance binding (mandatory):** canonical ref path + commit/run binding + hash linkage.
2. **PR `WARN` fail-close (mandatory):** either block outright or require explicit governed override artifact.
3. **Exhaustive degraded detection policy (mandatory):** block PR when changed-path resolution cannot prove full governed surface coverage.
4. **Selection mapping completeness guard (recommended):** governed-prefix unmatched paths must block.
5. **Semantics-level workflow tests (recommended):** execute trust-check snippets with crafted artifacts.

---

## 8) Mandatory-before-roadmap status

- **Mandatory before next roadmap phase:** Findings 1, 2, 3.
- **Recommended hardening before larger scale-up:** Findings 4, 5.

---

## Test and evidence coverage notes

- Verified relevant seam tests pass locally for current logic.
- Existing tests demonstrate intent and many fail-closed branches, but they do not fully prove end-to-end workflow runtime integrity against forged/stale artifact references or degraded-detection WARN paths.
- Therefore, absence of additional critical findings here does **not** constitute proof of non-exploitability under all GitHub runner edge conditions.
