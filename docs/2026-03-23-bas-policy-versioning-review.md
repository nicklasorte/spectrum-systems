# BAS Policy Versioning System — Surgical Implementation Review

- **Published:** 2026-03-23
- **Review date of request:** 2026-03-22
- **Decision:** **FAIL**
- **Trust assessment:** **NO**

## Scope reviewed
- `spectrum_systems/modules/**/policy*.py`
- `spectrum_systems/modules/**/version*.py`
- `spectrum_systems/modules/runtime/`
- `contracts/schemas/*policy*.json`
- `contracts/schemas/*config*.json`
- `contracts/schemas/*decision*.json` where policy linkage appears
- tests relevant to policy loading, policy version linkage, and decision artifacts

## Critical Findings (max 5)

### 1) Silent control-chain fallback can ignore stage policy bindings
- **What is wrong:** `_resolve_policy_for_stage()` calls `resolve_effective_slo_policy(stage=stage, policy_override=None)` with an invalid kwarg and then catches all exceptions to return `DEFAULT_POLICY`.
- **Why dangerous:** stage binding hardening can be silently bypassed.
- **Location:** `spectrum_systems/modules/runtime/control_chain.py` (`_resolve_policy_for_stage`)
- **Realistic failure scenario:** registry stage bindings are tightened, but control-chain continues using permissive fallback without surfacing a hard failure.

### 2) Core SLO artifacts are not version-pinned to immutable policy identity
- **What is wrong:** enforcement/gating/control-chain artifacts carry policy **name** only (`enforcement_policy`), not `policy_id` + `policy_version` (or immutable registry hash/version).
- **Why dangerous:** two semantically different policy definitions can produce artifacts that appear equivalent.
- **Location:** `contracts/schemas/slo_enforcement_decision.schema.json`, `contracts/schemas/slo_gating_decision.schema.json`, `contracts/schemas/slo_control_chain_decision.schema.json`; corresponding builders in runtime modules.
- **Realistic failure scenario:** policy profile behavior changes over time under same name; replay/audit cannot prove which exact policy definition governed a historical decision.

### 3) Schema-valid artifacts can still be policy-ambiguous
- **What is wrong:** runtime emits placeholders like `"(unknown)"`; gating/control-chain schemas allow generic non-empty strings for policy linkage.
- **Why dangerous:** artifacts pass schema while remaining semantically unauditable on policy identity.
- **Location:** `spectrum_systems/modules/runtime/decision_gating.py`, `spectrum_systems/modules/runtime/control_chain.py`, matching decision schemas.
- **Realistic failure scenario:** malformed upstream payload yields downstream schema-valid decisions with unknown policy linkage, creating false confidence in audit trails.

### 4) Replay consistency can miss policy drift due to nullable linkage
- **What is wrong:** replay decision analysis schema allows null `enforcement_policy`; replay recomputation often sets `None`; comparator skips policy comparisons when either side is missing.
- **Why dangerous:** policy/config drift can be under-detected and reported as consistent.
- **Location:** `contracts/schemas/replay_decision_analysis.schema.json`, `spectrum_systems/modules/runtime/replay_decision_engine.py`.
- **Realistic failure scenario:** replay runs under changed policy behavior but analysis omits policy linkage and still reports consistency.

### 5) Implicit runtime default policies remain in governance paths
- **What is wrong:** decision gating falls back to built-in stage postures on config load/validation errors; replay governance uses in-code `_DEFAULT_POLICY` when no policy is provided.
- **Why dangerous:** behavior can be driven by code constants instead of explicit, pinned policy artifacts.
- **Location:** `spectrum_systems/modules/runtime/decision_gating.py`, `spectrum_systems/modules/runtime/replay_governance.py`.
- **Realistic failure scenario:** missing/invalid policy config still yields enforceable outcomes via fallback defaults rather than halting decision-grade execution.

## Required Fixes (minimal, surgical)
1. Fix `_resolve_policy_for_stage()` to call resolver with correct signature and fail closed on resolver failure.
2. Add immutable policy identity fields (`policy_id`, `policy_version`, and/or registry hash/version) to enforcement, gating, and control-chain artifacts/schemas.
3. Tighten schemas to reject placeholder/ambiguous policy linkage (`"(unknown)"`) on governed paths.
4. Require non-null policy linkage for replay comparisons where enforcement decision exists; compare policy linkage deterministically.
5. Replace implicit governance fallbacks with explicit fail-closed behavior (or explicit blocked status) for decision-grade paths.

## Optional Improvements
- Add invariant tests ensuring stage-binding changes affect control-chain effective policy.
- Add parity tests across enforcement → gating → control-chain for exact policy linkage consistency.
- Add explicit `fallback_used` + `fallback_reason` fields where fallback is unavoidable, and require escalation for decision-bearing stages.

## Failure Mode Summary
Worst realistic failure: silent policy drift produces schema-valid but policy-ambiguous decision artifacts; replay may classify outcomes as consistent despite changed governing policy behavior, undermining trust and audit defensibility.
