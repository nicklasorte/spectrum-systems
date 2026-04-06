# PQX Architecture Review — 2026-04-05

## Review Metadata
- **Review date:** 2026-04-05
- **Scope:** PQX as governed execution spine (boundedness, deterministic sequencing, fail-closed behavior, replay/proof closure, governance boundaries, promotion/certification safety)
- **Reviewer:** Codex
- **Files/surfaces inspected:**
  - `spectrum_systems/modules/runtime/pqx_sequence_runner.py`
  - `spectrum_systems/modules/runtime/pqx_sequential_loop.py`
  - `spectrum_systems/modules/runtime/pqx_slice_runner.py`
  - `spectrum_systems/modules/runtime/pqx_required_context_enforcement.py`
  - `spectrum_systems/modules/runtime/pqx_proof_closure.py`
  - `spectrum_systems/modules/runtime/pqx_fix_gate.py`
  - `spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py`
  - `spectrum_systems/modules/governance/done_certification.py`
  - `spectrum_systems/modules/governance/promotion_gate_attack.py`
  - `tests/test_pqx_sequence_runner.py`
  - `tests/test_pqx_sequential_loop.py`
  - `tests/test_pqx_required_context_enforcement.py`
  - `tests/test_pqx_proof_closure.py`
  - `tests/test_done_certification.py`
  - `tests/test_promotion_gate_attack.py`
  - `docs/reviews/2026-04-02-pqx-red-team-security-audit.md`

## 1. Overall Assessment
**Verdict: conditionally sound.**

PQX is no longer structurally loose. It enforces ordered admission, dependency checks, resumable deterministic state, and explicit stop/block conditions. Core execution seams are mostly fail-closed and test-covered.

However, it is not yet “trust-by-default” as the canonical execution spine. The strongest residual risks are policy defaults and proof/certification composition behavior that can produce governable-but-weaker outcomes unless strict policy flags are explicitly set.

## 2. Critical Risks (Ranked)

1. **Done-certification defaults are permissive for warning-grade posture** (critical governance risk).
   - `allow_warn_as_pass` defaults to `true`, `require_system_readiness` defaults to `false`; this can permit certification under degraded readiness unless callers override policy explicitly.
   - This is not a code bug; it is a trust posture default that can become a fail-open governance seam if reused without strict policy wrappers.

2. **Proof-closure can synthesize fallback evidence labels for missing refs** (critical proof-integrity risk if upstream quality drifts).
   - In `build_execution_closure_record`, missing `eval_summary_ref`, `control_decision_ref`, `enforcement_action_ref`, and `replay_ref` are backfilled with synthetic placeholders (`<slice_id>:...`) rather than hard-failing.
   - This preserves pipeline continuity but weakens “only real evidence” guarantees.

3. **Commit-range inspection preflight allows governed work in unknown authority state** (critical if misapplied beyond preflight).
   - `commit_range_inspection` with `execution_context="unspecified"` returns allow + `authority_state="unknown_pending_execution"`.
   - Intended for inspection, but risky if downstream callers treat this as execution authorization instead of preflight posture.

## 3. Structural Weaknesses
- **Implicit orchestration spread across many modules** (`sequence_runner`, `sequential_loop`, `slice_runner`, `done_certification`, `proof_closure`) increases integration drift risk even with strong local checks.
- **Audit narrative includes synthesized markers** (`bundle_audit_status="synthesized"`, synthetic chain refs) that are operationally useful but weaker than hard artifact derivation.
- **Review gate “warn” path still progresses execution** (with degraded marker). This is deliberate but should be tightly policy-controlled in production governance profiles.

## 4. Execution Boundedness Assessment
**Assessment: safely bounded with explicit continuation controls.**

Evidence:
- Ordered non-empty slice input enforced; duplicates rejected.
- Admission rejects unsatisfied dependencies fail-closed.
- Main loop has explicit terminal states (`COMPLETED_ALL_SLICES`, multiple `BLOCKED_*`, `PAUSED_MAX_SLICES`).
- `max_slices` enforces bounded pause for resumable execution.
- Resume requires identity match (`queue_run_id`/`run_id`/`trace_id`) and admitted input hash consistency.

Residual risk:
- Boundedness is robust in code, but operationally depends on strict caller discipline for policy flags (`review_gate_required`, certification policy).

## 5. Sequence / State Integrity Assessment
**Assessment: strong, deterministic, and sequence-safe.**

Evidence:
- Deterministic hashing for admission/run fingerprint.
- Transition continuity checks and persisted reload exactness checks.
- Explicit TPA phase ordering validation (`plan->build->simplify->gate`) where applicable.
- Post-enforcement completion confirmation seam (`confirm_slice_completion_after_enforcement_allow`) avoids premature final completion.
- Trace invariants enforce required refs and final-status coherence.

Residual risk:
- Cross-module state semantics remain complex; risks are more integration complexity than missing checks.

## 6. Fail-Closed Assessment
**Assessment: mostly fail-closed, with one intentional preflight exception that must remain scoped.**

Evidence:
- Required wrapper/context/authority posture checks block governed execution on malformed/missing data.
- Review gate freeze/block halts progression.
- Done certification and promotion gate attack paths block malformed/missing/tampered certification artifacts.
- Fix gate requires exact pending-finding linkage and blocks unresolved/mismatched fixes.

Fail-open seam to monitor:
- `commit_range_inspection` mode allows unknown authority state for inspection workflows; safe only if never treated as execution grant.

## 7. Replay / Reproducibility Assessment
**Assessment: good replay determinism in core execution; medium risk in proof-evidence strictness.**

Evidence:
- Deterministic trace IDs and canonical hash identity surfaces.
- Replay linkage checks in done certification validate trace consistency across replay/regression/control/cert pack.
- Promotion attack tests validate block behavior for malformed/missing/mismatched certifications.

Residual risk:
- Proof closure’s fallback synthetic refs may permit “replay-claim completeness” with weaker-than-ideal raw evidence linkage.

## 8. Trace / Proof / Certification Assessment
**Assessment: enforceable but not maximally strict.**

Strengths:
- Hard-gate falsification record requires explicit condition checks and trace links.
- Bundle certification requires passed falsification + verified replay + assertion set.
- Trace invariants in sequential loop reject inconsistent terminal narratives.

Weakness:
- Execution closure accepts fallback synthetic per-slice evidence labels when some refs are absent; this should be hardened if PQX is the authoritative truth spine.

## 9. Governance Boundary Assessment
**Assessment: governance-aligned by design, conditionally strong at runtime.**

Strengths:
- Governed context enforcement rejects contradictory wrapper/governance posture.
- Promotion boundary actively red-teams done-cert bypass classes.
- Bundle/readiness/fix gates prevent blind progression.

Boundary risk:
- Default done-certification policy is not strict-by-default, so boundary strength can be caller-dependent.

## 10. Operational Usefulness Assessment
**Assessment: usable as canonical spine today, but only with strict policy profile and monitoring.**

Why usable:
- Deterministic sequence execution is implemented, test-covered, and resumable.
- Governance artifacts are explicit and machine-validated.
- Attack-oriented promotion tests exist and pass.

Why conditional:
- Trust posture currently relies on policy discipline to avoid permissive defaults and synthetic-evidence overuse.

## 11. Recommended Fixes (Rack and Stack)

### Fix now
1. **Harden done-certification defaults for spine mode:** default `require_system_readiness=true`; default `allow_warn_as_pass=false` for governed PQX profile.
2. **Require strict evidence mode in proof closure:** disallow synthetic fallback refs when `execution_spine_mode=authoritative`.
3. **Guard preflight allowance:** ensure `unknown_pending_execution` from commit-range inspection cannot be consumed by execution admission.

### Fix next
1. Add explicit “strict governance profile” artifact consumed by sequence runner + done certification, so strictness is explicit and versioned.
2. Add integration tests that fail if inspection-mode allow is accidentally accepted in execution paths.
3. Add a closure integrity score (real refs vs synthetic refs) as a blocking threshold for promotion.

### Monitor only
1. Cross-module orchestration drift between sequence runner, sequential loop, and done certification.
2. Growth in synthesized audit markers vs first-class artifacts.
3. Policy override entropy across scripts/CLIs invoking PQX.

## 12. What NOT to Change
- Do **not** remove deterministic hash identities and persisted continuity checks.
- Do **not** collapse explicit blocked states into implicit exceptions; blocked artifacts are governance-critical evidence.
- Do **not** weaken promotion attack validation; this is one of the strongest trust-boundary tests in the stack.
- Do **not** replace explicit admission/dependency checks with “best effort” scheduling.

## 13. Long-term Risk Register

### Top 3 unsafe evolution risks
1. Policy defaults drifting toward permissive pass-through under delivery pressure.
2. Reintroducing implicit continuation shortcuts that bypass explicit blocked-state artifacts.
3. Allowing synthetic proof references to substitute for real execution truth in promotion decisions.

### Top 3 bureaucracy/slowness risks
1. Over-layering gates without profile-based tuning (execution throughput collapse).
2. Excessive artifact fan-out per slice causing operational overhead and debugging latency.
3. Gate duplication across sequence, bundle, and certification surfaces without consolidation.

### Top 3 silent trust-loss risks
1. Teams treating warning-grade certification as equivalent to fully healthy certification.
2. Inspection-mode allowances being mistaken for execution authorization.
3. Audit consumers trusting closure artifacts without checking whether evidence refs are real vs synthesized.
