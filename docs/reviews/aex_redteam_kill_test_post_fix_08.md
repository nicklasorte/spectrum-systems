# AEX Kill Test (Post FIX-08) — 2026-04-09

## 1. Executive Verdict
- Is the invariant breakable?
- NO

## 2. Attack Results

### Attack 1 — Capability vs intent
- result
  - FAILED (no bypass)
- explanation
  - The boundary rejects missing/unknown intent, then independently enforces lineage whenever PQX has repo-write capability via `state_path` or `runs_root`, even if `execution_intent="non_repo_write"`.
  - `_requires_repo_write_lineage(...)` returns true for repo-controlled paths regardless of declared intent.
  - Verified by execution tests that explicitly set `execution_intent="non_repo_write"` with repo-controlled runtime paths and get `REPO_WRITE_LINEAGE_REQUIRED`.

### Attack 2 — Replay
- result
  - FAILED (replay blocked)
- explanation
  - Replay protection consumes a lineage token into both in-memory state and a persistent registry file (`state/repo_write_lineage_consumed_tokens.json`).
  - Second use of the same lineage token fails with `lineage_replay_detected`.
  - Cross-process-like replay is blocked because the persistent token registry is read on each validation attempt.

### Attack 3 — Forgery
- result
  - FAILED (forgery blocked)
- explanation
  - Manual issuance from non-authoritative runtime call sites fails (`authenticity_boundary_issuer_forbidden`) due to issuance caller-bound checks.
  - Even cryptographically valid authenticity material is insufficient without a matching authoritative issuance registry record. Validation fails on `lineage_issuance_missing` or mismatch.
  - Issuance registry verification binds artifact identity + issuer + key + digest + request/trace continuity.

### Attack 4 — Partial lineage
- result
  - FAILED (partial/mismatch blocked)
- explanation
  - Missing artifacts, missing authenticity, wrong issuer/key binding, stale/invalid timestamps, bad audience/scope, continuity mismatches, missing issuance proof, and issuance-record tampering all fail closed.
  - Validation requires all three artifacts (`build_admission_record`, `normalized_execution_request`, `tlc_handoff_record`) plus authenticity + issuance proof + continuity + freshness.

### Attack 5 — Path misclassification
- result
  - FAILED (misclassification blocked in tested classes)
- explanation
  - Repo-control detection resolves paths canonically and checks containment under repo root.
  - Symlink-to-repo cases are treated as repo-controlled and require lineage.
  - Lexical intent dodge (`non_repo_write`) does not bypass when path capability indicates repo-write risk.

### Attack 6 — Drift scenario
- result
  - HIGH (realistic future fragility)
- explanation
  - Boundary strength today is good, but the weakest drift vector is issuance authority scope: `_AUTHORIZED_ISSUANCE_CALLERS` is a hardcoded stack-identity allowlist.
  - A developer can extend this allowlist or alter caller topology and accidentally authorize new lineage minting surfaces; current tests prove blocking for one non-authoritative call path but do not lock the exact authorized-caller set.
  - Direct `run_pqx_slice` caller drift is better protected by structural tests that enforce exact caller set + mandatory `execution_intent`, so that specific bypass is less likely to slip.

## 3. Weakest Point
- The most fragile component is stack-inspection-based issuance authority (`lineage_authenticity._AUTHORIZED_ISSUANCE_CALLERS` + `_enforce_boundary_issuance_authority`). It is effective now but sensitive to refactors and allowlist drift.

## 4. Final Recommendation
- SAFE TO MOVE ON
