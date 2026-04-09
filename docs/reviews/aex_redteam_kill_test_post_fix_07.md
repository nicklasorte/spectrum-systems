# AEX Kill Test (Post FIX-07) — 2026-04-09

## 1. Executive Verdict
- Is the invariant breakable? **YES**.
- The boundary is still breakable because forged lineage can be minted and accepted at PQX using runtime-accessible issuer secrets, without authoritative AEX/TLC issuance.

## 2. Attack Results

### Attack 1 — Capability vs intent
- **result:** ATTACK FAILED.
- **explanation:** Declaring `execution_intent="non_repo_write"` does not bypass lineage when `state_path` or `runs_root` resolve under repo control. `run_pqx_slice(...)` calls `_enforce_repo_write_lineage_boundary(...)`, which calls `_requires_repo_write_lineage(...)`; repo-controlled canonical paths force lineage regardless of declared intent. Attempted repo-root `state_path`/`runs_root` without lineage blocked with `REPO_WRITE_LINEAGE_REQUIRED`. Supplying valid lineage with the same non-repo intent completed.

### Attack 2 — Replay
- **result:** ATTACK FAILED.
- **explanation:** Replay was rejected across process-like boundaries. Token consumption persists in `state/repo_write_lineage_consumed_tokens.json`; second use of the exact same lineage in a fresh Python invocation failed with `repo_write_lineage_rejected:lineage_replay_detected`.

### Attack 3 — Forgery
- **result:** ATTACK SUCCEEDED (**BLOCKER**).
- **explanation:** I manually constructed all three artifacts (`build_admission_record`, `normalized_execution_request`, `tlc_handoff_record`) and generated authenticity blocks by directly reproducing the attestation algorithm with runtime-reachable environment secrets (`SPECTRUM_LINEAGE_AUTH_SECRET_AEX`, `SPECTRUM_LINEAGE_AUTH_SECRET_TLC`) and key IDs.

  Exact exploit path:
  1. Build schema-valid lineage artifacts with internally consistent `request_id`/`trace_id`/refs.
  2. Compute `payload_digest` over canonical payload.
  3. Build `scope` and timestamps/freshness fields.
  4. Compute HMAC attestation with issuer secret from environment.
  5. Insert authenticity material and submit to PQX boundary with `execution_intent="non_repo_write"` but repo-controlled `state_path`/`runs_root`.
  6. PQX accepts lineage and executes (`status=complete`).

  Root cause: validation verifies cryptographic correctness and issuer string/key binding, but does not prove issuance provenance. Issuance-authority stack checks exist in `issue_authenticity(...)`, but `validate_repo_write_lineage(...)`/`verify_authenticity(...)` accept any artifact that verifies against secrets.

### Attack 4 — Partial lineage
- **result:** ATTACK FAILED.
- **explanation:** Partial lineage did not pass. Removing required artifacts or authenticity blocks failed at schema and/or authenticity validation (for example: missing `authenticity` field rejected fail-closed).

### Attack 5 — Path misclassification
- **result:** ATTACK FAILED.
- **explanation:** Lexical and symlink tricks were blocked. `state/../state/...` still canonical-resolved into repo and triggered lineage enforcement. Symlinked external path pointing into repo also triggered lineage enforcement. Canonical resolution logic remained fail-closed in tested cases.

### Attack 6 — Drift scenario
- **result:** HIGH.
- **explanation:** A realistic bypass can be reintroduced without touching `run_pqx_slice(...)`: any new caller or wrapper that can access lineage secrets can mint synthetic lineage offline and feed it to PQX, passing current verification. Existing tests heavily cover replay/path checks but do not establish unforgeable issuer provenance at verification time. Result: likely future regressions will still pass tests while preserving the same forged-lineage exploit class.

## 3. Weakest Point
- **Single most fragile component:** authenticity trust model in `verify_authenticity(...)` / `validate_repo_write_lineage(...)`.
- It is secret-possession based, not authority-origin based. If runtime can read issuer secrets, the attacker can mint “valid” lineage without AEX/TLC.

## 4. Final Recommendation
- **DO NOT MOVE ON**.
