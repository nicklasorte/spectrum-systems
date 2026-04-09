# AEX Kill Test (Post FIX-06) — 2026-04-09

## 1. Executive Verdict
- Is the invariant breakable? **YES**.

The boundary is still breakable at the PQX seam. I executed repo-mutating-capable PQX paths without legitimate system-issued lineage by exploiting (a) forgeable authenticity model, (b) process-local replay tracking, and (c) repo-path classification blind spots.

## 2. Attack Results

### Attack 1 — Capability vs intent
- **result:** **FAIL (attack blocked in tested direct seam path).**
- **explanation:**
  - `run_pqx_slice(...)` calls `_enforce_repo_write_lineage_boundary(...)` before execution.
  - `_requires_repo_write_lineage(...)` forces lineage when either `execution_intent == "repo_write"` **or** `state_path`/`runs_root` classify as repo-controlled.
  - Practical run: `execution_intent="non_repo_write"` + repo-contained paths + no lineage returned `REPO_WRITE_LINEAGE_REQUIRED` (blocked).
  - This specific bypass is closed **only when repo-path classification is correct**.

### Attack 2 — Replay
- **result:** **SUCCESS (BLOCKER).**
- **explanation:**
  - Same-process replay is blocked (`lineage_replay_detected`) because tokens are cached in a module-level in-memory set.
  - Cross-process replay succeeds because replay state is not persisted:
    1. Run process #1 with valid lineage → execution completes.
    2. Run process #2 with the exact same lineage JSON → execution also completes.
  - This violates non-reuse invariants for any real multi-process invocation surface (CLI/worker restart/parallel workers).

### Attack 3 — Forgery
- **result:** **SUCCESS (BLOCKER).**
- **explanation:**
  - I manually constructed all three lineage artifacts and signed them using the runtime helper/algorithm and attacker-controlled issuer secrets exposed through environment variables.
  - `validate_repo_write_lineage(...)` accepted these forged artifacts and `run_pqx_slice(... execution_intent="repo_write")` completed.
  - Authenticity currently proves only “knows current symmetric issuer secret in process env,” not “issued by authoritative AEX/TLC control-plane identities.”

### Attack 4 — Partial lineage
- **result:** **FAIL (attack blocked).**
- **explanation:**
  - Missing artifact(s) fail closed (`normalized_execution_request_required`, etc.).
  - Missing authenticity and freshness also fail through `verify_authenticity(...)` checks.
  - No partial lineage variant passed in the tested seam path.

### Attack 5 — Path misclassification
- **result:** **SUCCESS (BLOCKER).**
- **explanation:**
  - Repo-boundary detection uses lexical `Path.relative_to(REPO_ROOT)` on provided path text and does not canonicalize symlink targets.
  - Exploit path:
    1. Create symlink outside repo (`/tmp/.../state_link.json`) targeting a repo file.
    2. Invoke `run_pqx_slice(... execution_intent="non_repo_write", state_path=<outside symlink>, runs_root=<outside path>)` without lineage.
    3. Boundary classifies as non-repo path, skips lineage, and execution writes through symlink into repo-controlled target.
  - This is a direct trust-boundary break through path classification.

### Attack 6 — Drift scenario
- **result:** **HIGH.**
- **explanation:**
  - Current structural tests assert only that direct callers include the `execution_intent` keyword, not that call sites prevent path-classification abuse, use canonicalized path checks, or enforce issuance trust semantics.
  - A new caller can pass `execution_intent="non_repo_write"`, route I/O via symlink/out-of-repo lexical paths, and evade lineage while still mutating repo-controlled content.
  - Replay guarantees also regress silently across process boundaries because tests are currently process-local by default.

## 3. Weakest Point
- **Single most fragile component:** authenticity + replay trust model at runtime boundary.
  - Authenticity is symmetric-secret based and process-environment scoped, so lineage can be minted by any actor with secret-setting ability in the execution environment.
  - Replay protection is in-memory only, so it does not survive process boundaries.

## 4. Final Recommendation
- **DO NOT MOVE ON**
