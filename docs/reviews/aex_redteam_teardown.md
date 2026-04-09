# AEX Red-Team Teardown — 2026-04-09

## 1. Executive Verdict
- **Is the system actually secure?** No.
- **Can the invariant be broken?** Yes. **BLOCKER**.
- **Verdict:** The current boundary enforces *syntax-valid lineage + shared-secret knowledge*, not trusted system issuance. Because the fallback HMAC secret is hardcoded and globally reusable, an attacker can mint fully valid AEX/TLC lineage offline and execute `repo_write` intent through `run_pqx_slice(...)`.

### Required Questions (explicit answers)
1. **Can you execute repo-mutating PQX work without authentic AEX lineage?** Yes.
2. **If yes, exact steps?** See Successful Attack A1 below (forged lineage with default secret).
3. **If no, closest path?** Not applicable; direct bypass succeeded.
4. **Is authenticity trustworthy or just harder to fake?** Just harder to fake when secret hygiene is perfect; currently it is trivially forgeable.
5. **Weakest part of authenticity chain?** Shared-secret management (hardcoded default + broad process access).
6. **What breaks first under real-world usage?** Secret sprawl and caller drift around `execution_intent` classification.
7. **If malicious, how target system?** Forge lineage using known default secret; submit `execution_intent="repo_write"`; optionally replay captured lineage across runs.
8. **Is invariant truly enforced or only suggested?** Only strongly suggested; enforcement can be bypassed by minting counterfeit-but-valid authenticity.

## 2. Successful Attacks (if any)

### A1 — Forged lineage with valid HMAC using built-in default secret (**BLOCKER**)
**Goal:** run PQX with `execution_intent="repo_write"` and no legitimate AEX/TLC issuance.

**Exact steps executed:**
1. Manually constructed `build_admission_record`, `normalized_execution_request`, and `tlc_handoff_record` with schema-valid fields.
2. Reimplemented attestation format exactly: `HMAC_SHA256(secret, "{issuer}|{key_id}|{payload_digest}")`.
3. Used repository-default secret:
   - `SPECTRUM_LINEAGE_AUTH_SECRET` fallback = `spectrum-lineage-auth-secret-v1`
   - `key_id` fallback = `local-system-v1`
4. Called `run_pqx_slice(... execution_intent="repo_write", repo_write_lineage=<forged>)`.
5. Result returned: `status = complete`.

**Why it works:**
- Authenticity verifier accepts any artifact signed with current process secret; it does not prove issuance provenance beyond shared-key possession.
- Default secret is hardcoded and predictable.
- No key registry / rotation / revocation / issuer-specific key separation is enforced.

### A2 — Replay / context re-use of lineage artifacts (**HIGH**)
**Result:** Reuse is possible.

**Why it works:**
- No nonce, expiration, audience binding, or run binding is enforced in authenticity.
- Validation checks internal consistency (`trace_id`, `request_id`, refs) but not freshness or one-time use.
- A previously valid lineage bundle can be replayed for later execution contexts if passed unchanged.

## 3. Near-Miss Attacks

### N1 — Canonicalization mismatch attack
**Attempt:** mutate signed payload while preserving digest via serialization differences.
**Outcome:** failed in current code path; canonical JSON hashing is deterministic for parsed dict payloads.
**What stopped it:** digest recomputation over artifact (minus `authenticity`) catches post-signing mutation.

### N2 — Cross-artifact mismatch with inconsistent refs
**Attempt:** mix records from different runs.
**Outcome:** failed when `request_id`, `trace_id`, and refs disagree.
**What stopped it:** strict lineage cross-checks in `validate_repo_write_lineage`.

### N3 — Post-sign field tamper
**Attempt:** change behavior-driving field after signing.
**Outcome:** failed; payload digest mismatch trips verification.
**What stopped it:** authenticity covers full artifact payload except authenticity block itself.

## 4. Authenticity Model Assessment
- **Is HMAC approach sufficient?** Not in the current deployment model.
- **Current model quality:** integrity check only; provenance is weak because issuer and verifier share a static symmetric secret.
- **Weak points:**
  1. Hardcoded default secret (predictable, universal).
  2. No trust anchor proving *which component* issued artifact.
  3. `key_id` is not verified against an issuer-bound key registry.
  4. No anti-replay controls (nonce/expiry/audience/run binding).
  5. Secret likely reachable by any in-process caller/script, enabling unauthorized minting.

## 5. Weakest Link
**Single most dangerous component:** `lineage_authenticity` secret model (static shared symmetric secret with hardcoded fallback).

This collapses “verifiable system issuance” into “whoever knows one string,” which is not a trustworthy issuance boundary in a multi-caller evolving codebase.

## 6. Drift Scenarios
1. **Caller drift (HIGH):** future wrapper marks `execution_intent="non_repo_write"` while introducing write-capable behavior in the same path; lineage boundary is skipped.
2. **Secret sprawl (HIGH):** more scripts/services import or copy secret usage to unblock tests/ops, expanding minting authority unintentionally.
3. **Replay institutionalization (MEDIUM→HIGH):** operators begin reusing cached lineage artifacts for convenience; eventually becomes accepted operational practice.
4. **Auth contract cargo-culting (MEDIUM):** teams validate presence of authenticity fields but not issuance controls, preserving false sense of security.

## 7. Required Fixes
Minimal and surgical only:
1. **Remove insecure default secret immediately** (fail closed if `SPECTRUM_LINEAGE_AUTH_SECRET` unset).  
2. **Issuer-scoped keying:** separate AEX and TLC keys; enforce `issuer -> allowed key_id` mapping at verify time.  
3. **Replay binding:** add signed `issued_at`, short TTL, and audience/context binding (`execution_boundary`, `repo`, `step_id` or run scope).  
4. **One-time lineage tokening for repo_write:** persist consumed lineage IDs and reject second use.  
5. **Guardrail test additions:** adversarial test that forges lineage with known default secret must fail; replay test must fail on second use.

## 8. Final Recommendation
**DO NOT MOVE ON**

Reason: invariant can be violated today via practical forged-lineage execution, and replay resistance is absent.
