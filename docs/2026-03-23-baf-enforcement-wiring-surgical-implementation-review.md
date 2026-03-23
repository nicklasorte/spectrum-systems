# BAF Enforcement Wiring — Surgical Implementation Review
**Date:** 2026-03-23
**Reviewer:** Codex (GPT-5.2-Codex)

## Scope Reviewed
- `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py` *(repo contains this module name in place of `evaluation_enforcement.py`)*
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `scripts/run_evaluation_control_loop.py`
- `contracts/schemas/evaluation_enforcement_action.schema.json`
- `tests/test_evaluation_control_loop.py`
- `tests/test_evaluation_enforcement_bridge.py` *(repo contains this test name in place of `tests/test_evaluation_enforcement.py`)*

---

## Decision

**FAIL**

BAF enforcement is not semantically aligned to canonical control-loop decision vocabulary. The control-loop path is canonical (`allow|warn|freeze|block`), but enforcement bridge and enforcement-action schema remain legacy-vocabulary-centric (`allow_with_warning|freeze_changes|block_release|require_review`) and actively tested as such.

---

## Critical Findings (max 5)

### 1) Canonical response misalignment at enforcement boundary
- **What is wrong:** Enforcement bridge only treats legacy response set as valid and maps only those values to action types.
- **Why dangerous:** Canonical control-loop decisions can fail at enforcement translation despite being valid governed artifacts.
- **Location:** `evaluation_enforcement_bridge.py` constants and `build_enforcement_action` validation.
- **Realistic failure scenario:** A canonical decision with `system_response="warn"` is accepted by control-loop schema but rejected by enforcement bridge as unknown.

### 2) Dual-schema acceptance creates semantic ambiguity
- **What is wrong:** Budget decision schema uses `oneOf` with both legacy and control-loop branches.
- **Why dangerous:** Multiple producers can emit semantically different yet schema-valid `system_response` values into a single enforcement boundary.
- **Location:** `contracts/schemas/evaluation_budget_decision.schema.json`.
- **Realistic failure scenario:** One pipeline emits `freeze`; another emits `freeze_changes`; enforcement behavior differs by producer version, not by risk state.

### 3) Enforcement action schema remains legacy-typed
- **What is wrong:** `action_type` enum still includes legacy actions and excludes canonical `freeze`/`block`.
- **Why dangerous:** Schema-valid actions can be semantically incompatible with canonical consumers.
- **Location:** `contracts/schemas/evaluation_enforcement_action.schema.json`.
- **Realistic failure scenario:** Downstream control expecting canonical `block` misses a `block_release` action and applies inconsistent policy.

### 4) Legacy behavior is reinforced by tests
- **What is wrong:** Enforcement tests assert legacy mappings (e.g., `allow_with_warning -> warn`, `freeze_changes`, `block_release`, `require_review`) as expected behavior.
- **Why dangerous:** CI passes while preserving drift from canonical governance vocabulary.
- **Location:** `tests/test_evaluation_enforcement_bridge.py`.
- **Realistic failure scenario:** Future changes that keep legacy behavior continue to pass CI, masking canonical non-compliance.

### 5) Fail-closed is present for unknown/invalid inputs, but canonical semantics still fail operationally
- **What is wrong:** Unknown response paths raise or block (fail-closed), but canonical values are currently treated as unknown by enforcement bridge.
- **Why dangerous:** This is not fail-open, but it is enforcement incompatibility at the trust boundary.
- **Location:** `evaluation_enforcement_bridge.py` unknown response handling and enforce flow.
- **Realistic failure scenario:** Production control-loop emits canonical `block`; enforcement bridge raises and aborts instead of producing consistent canonical enforcement action.

---

## Required Fixes

1. **Canonicalize enforcement bridge vocabulary**
   - Restrict accepted `system_response` to `allow|warn|freeze|block`.
   - Remove legacy literals from `_VALID_SYSTEM_RESPONSES`, `_RESPONSE_TO_ACTION_TYPE`, `_BLOCKING_RESPONSES`, `_REVIEW_RESPONSES`, and `_build_required_human_actions` branches.

2. **Canonicalize enforcement-action schema**
   - Update `action_type` enum and conditional invariants to canonical values.
   - Keep strict `allowed_to_proceed` invariants (`allow/warn=true`, `freeze/block=false`).

3. **Remove dual-vocabulary ambiguity on BAF path**
   - For enforcement entry path, accept only canonical decision artifacts (or split legacy path explicitly and deprecate it).

4. **Update tests to canonical expectations only**
   - Replace legacy mapping cases and add explicit rejection tests for legacy responses.

---

## Optional Improvements

- Add a single parameterized mapping test that enforces one-to-one deterministic mapping of canonical decisions to actions.
- Add explicit negative tests for missing `system_response`, malformed decision artifacts, and malformed override artifacts to ensure hard failure behavior remains stable.

---

## Trust Assessment

**NO**

---

## Failure Mode Summary

Worst realistic semantic drift: canonical control-loop artifacts are valid and produced upstream, but enforcement remains legacy-mapped; resulting bridge behavior rejects or mis-translates decisions at the trust boundary, causing governance inconsistency determined by vocabulary version rather than system risk state.
