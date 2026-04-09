# AEX Red-Team Teardown (Post FIX-05) — 2026-04-09

## 1. Executive Verdict

**Verdict: Invariant is still breakable.**

The boundary is materially stronger than pre-FIX-05 on signature checks, issuer/key binding, digest binding, and schema gating — but it is **not** a complete trust boundary yet.

Two realistic BLOCKER-class breaks remain:

1. **Intent-declaration bypass (non-repo-write path still mutates repository state/artifacts).**
2. **Replay acceptance at the PQX repo-write execution boundary because replay protection is explicitly disabled in boundary calls.**

The current system proves authenticity of provided lineage artifacts, but enforcement of *when lineage is required* is still partially declarative and can be downgraded by caller-controlled `execution_intent` / `repo_mutation_requested` posture.

---

## 2. Successful Attacks (if any)

### Attack A — Partial mutation via `execution_intent="non_repo_write"` (BLOCKER)

**What breaks:** “No repo-mutating PQX execution may proceed without authentic lineage issued by AEX/TLC.”

**Exact steps**

1. Call `run_pqx_slice(...)` directly with:
   - `execution_intent="non_repo_write"`
   - `repo_write_lineage=None`
   - normal runnable `step_id`, `roadmap_path`, writable `state_path`, `runs_root`.
2. Observe execution returns `status="complete"`.
3. Observe repository mutation still occurs (state/artifact files written under provided repo paths).

**Why this works**

- Boundary logic in `_enforce_repo_write_lineage_boundary` returns early (no lineage required) for `non_repo_write`.
- `run_pqx_slice` then writes multiple JSON artifacts and updates PQX state.
- Therefore execution mutates repository-controlled paths without AEX/TLC lineage.

**Severity:** **BLOCKER**

---

### Attack B — Replay of valid repo-write lineage at PQX execution boundary (BLOCKER)

**What breaks:** replay-protected lineage requirement at runtime boundary.

**Exact steps**

1. Mint one valid lineage triplet (`build_admission_record`, `normalized_execution_request`, `tlc_handoff_record`) with valid authenticity attestations.
2. Call `run_pqx_slice(..., execution_intent="repo_write", repo_write_lineage=<same_lineage>)` once.
3. Reuse the **exact same lineage artifacts** in a second call.
4. Second call still succeeds (`status="complete"`), no replay rejection.

**Why this works**

- The lineage guard has replay tracking (`lineage_token_id`) but `run_pqx_slice` invokes validation with `enforce_replay_protection=False`.
- So replay defense exists in the guard implementation, but is explicitly switched off at the PQX boundary call site.

**Severity:** **BLOCKER**

---

## 3. Near-Miss Attacks

### 1) Forgery attack (post FIX-05)

**Result:** failed (good hardening)

- Wrong issuer/key combinations fail on issuer binding and key-id checks.
- Payload tampering fails payload digest and attestation verification.
- Audience/scope/timestamp fields are validated fail-closed.

**Near miss:** secret exposure path still matters (see Secret misuse).

### 2) Replay attack

**Result:** succeeded at PQX boundary (BLOCKER) as above.

### 3) Partial mutation attack

**Result:** succeeded (BLOCKER) as above.

### 4) Cross-artifact mismatch attack

**Result:** mostly failed in direct lineage checks.

- Trace/request/ref continuity checks are strict.
- Mixed artifacts from different runs are usually rejected by request/trace/ref mismatches or digest mismatches.

**Near miss:** if caller avoids repo-write classification entirely, these continuity checks are never invoked.

### 5) Caller-based attack

**Result:** partially succeeded (HIGH).

- Several direct callers force `execution_intent="non_repo_write"` in default execution paths.
- Enforcement is not uniformly tied to an independent mutation detector; callers can route around lineage requirement by declaration posture.

### 6) Secret misuse attack

**Result:** practical risk remains (HIGH).

- Any in-process code path with access to `issue_authenticity(...)` and signer env secrets can mint “valid” lineage authenticity objects.
- This is not external compromise; this is broad in-repo capability exposure if runtime secrets are present.

### 7) Freshness / TTL attack

**Result:** mostly failed.

- `issued_at`, `expires_at`, max-age, future-skew, audience, scope are enforced.

**Near miss:** replay is still possible within freshness window when replay protection is disabled at boundary call sites.

### 8) Drift attack (future failure)

**Result:** likely under normal evolution (HIGH).

- The seam depends on convention: callers must correctly set `execution_intent` / `repo_mutation_requested`.
- New wrappers/scripts can accidentally (or deliberately) declare non-repo-write and still execute repo-touching paths.

---

## 4. Authenticity Model Assessment

Authenticity is now **cryptographically verifiable**, not just approximated:

- issuer + key binding
- payload digest binding over canonical payload
- HMAC attestation
- audience + scope constraints
- issued/expires/max-age checks

But the trust model still relies on these assumptions:

1. Callers cannot downgrade intent classification.
2. Replay protection is enabled at all enforcement boundaries.
3. Signing secrets are unavailable to unintended runtime paths.

Assumptions #1 and #2 are already violated in current runtime behavior.

---

## 5. Weakest Link

**Single most dangerous component:**

`run_pqx_slice` boundary posture coupling to caller-provided `execution_intent`, combined with replay disabled at that exact boundary call.

This is where “authenticity exists” and “authenticity is required and non-replayable” diverge.

---

## 6. Drift Forecast

Most likely degradation path:

1. New caller/wrapper added for convenience.
2. Defaults to `non_repo_write` for compatibility.
3. Still writes state/artifacts in repo-controlled paths.
4. Over time this becomes normalized execution behavior.
5. AEX/TLC lineage remains present in docs/tests for repo_write class, but practical mutation occurs through non-repo-write channels.

First thing that breaks under real usage: **classification integrity** (declarative intent diverges from actual mutation behavior).

---

## 7. Required Fixes

Minimal patch set only:

1. **Enforce replay at PQX boundary**
   - In `run_pqx_slice` repo-write lineage validation call, set `enforce_replay_protection=True`.
2. **Make lineage requirement capability-based, not declaration-based**
   - Treat any PQX path that writes repository state/artifacts as repo-write-class unless explicitly proven isolated.
   - At minimum: if `state_path`/`runs_root` resolve under repo root, require repo-write lineage.
3. **Constrain signing surface**
   - Centralize signing in narrow AEX/TLC boundary modules (or signer service) and block generic module-level minting in unrelated runtime code paths.

---

## 8. Final Recommendation

**DO NOT MOVE ON**

There are present-tense BLOCKER bypasses of the declared invariant.

---

## Required Questions (Explicit Answers)

1. **Can repo-mutating PQX execution be triggered without authentic lineage?**
   - **Yes.** By executing PQX with `execution_intent="non_repo_write"` (no lineage) while still writing state/artifacts under repo paths.

2. **If yes, show exact exploit steps.**
   - See Attack A and Attack B above.

3. **If no, what is the closest possible exploit?**
   - Not applicable (exploit exists).

4. **Is authenticity now truly verifiable or still approximated?**
   - **Verifiable cryptographically** for provided artifacts, but boundary application is incomplete.

5. **What is the weakest remaining component?**
   - Caller-controlled intent classification + replay disabled at the PQX enforcement call site.

6. **What breaks first under real-world usage?**
   - Classification integrity (non-repo-write declarations used on repo-touching execution paths).

7. **If malicious, how would you attack this system?**
   - Prefer non-repo-write caller paths that still mutate repo artifacts; if repo-write is required, replay previously valid lineage while replay check is off at boundary.

8. **Is the invariant now enforced or still partially dependent on convention?**
   - Still partially dependent on convention.

9. **Is AEX “done for now”?**
   - **No.** Boundary wiring remains bypassable in realistic in-repo runtime paths.
