# Claude Review 023 — Promotion Trust Spine Review

**Date:** 2026-04-01
**Reviewer:** Claude (claude-sonnet-4-6)
**Scope:** Surgical post-RED-021 review of promotion trust spine
**Branch:** claude/review-promotion-trust-spine-rOv9z

---

## Scope Reviewed

Primary surface:
- `spectrum_systems/orchestration/sequence_transition_policy.py` — the authoritative promotion gate
- `spectrum_systems/modules/runtime/replay_engine.py` — canonical and legacy replay paths
- `spectrum_systems/modules/runtime/evaluation_control.py` — decision mapping from replay evidence
- `spectrum_systems/orchestration/cycle_runner.py` — orchestration of certification and three_slice promotion
- `scripts/run_control_loop_certification.py` — gate proof construction and certification pack emission

Adjacent tests and fixtures reviewed:
- `tests/test_sequence_transition_policy.py`
- `tests/test_cycle_runner.py`
- `tests/test_control_loop_certification.py`
- `tests/test_replay_engine.py`
- `tests/fixtures/sequence_replay/indeterminate_paths.json`
- `tests/fixtures/autonomous_cycle/`

---

## What RED-021 Changed on the Promotion Path

Based on commit history and current code state, RED-021 hardened the following on the promotion trust spine:

1. Added `_promotion_authority_gate` to `evaluate_sequence_transition` — promotion now requires `replay_result_ref` and `policy_ref` from `done_certification_input_refs`, with the policy artifact read and its `decision`/`system_response` field evaluated for blocking values.
2. Added `_hard_gate_falsification_passes` — promotion now requires a `pqx_hard_gate_falsification_record` artifact with `overall_result == "pass"` and all 8+ checks individually passing.
3. Added optional consumption of `enforcement_result_ref` and `eval_coverage_summary_ref` — these are now checked if declared.
4. Added `control_allow_promotion` and `decision_blocked` as explicit manifest-level authorization flags.
5. Ordered all promotion checks deterministically with early-exit blocking.

---

## Architectural Judgment

**The promotion path is structurally improved but contains medium-risk bypass vectors that must be closed before more capability is built on top of it.**

The gate-proof structure is present and deterministic. The primary seam (`_promotion_authority_gate`) is fail-closed in the right places. However, there are two substantive gaps: (1) enforcement evidence is not required, only optional; (2) the gate-proof evidence in the certification script is constructed as a shallow boolean flip from a single ref, not as actual field-level proof. These create paths where promotion can proceed without enforcement obedience and with proof claims that have no structural backing.

---

## Findings

### Strengths

1. **`replay_result_ref` and `policy_ref` are hard-required.** `_promotion_authority_gate` blocks unconditionally if either is missing or unreadable. The policy is read and its content evaluated — this is substantive consumption, not a file-existence check.

2. **`policy_ref` content is evaluated against a blocking vocabulary.** The gate rejects `{"deny", "block", "freeze", "hold", "require_review"}` decisively.

3. **`_hard_gate_falsification_passes` is well-structured.** It requires correct `artifact_type`, `overall_result == "pass"`, and all individual checks passing. The fallback resolution chain from `certification_pack.gate_proof_evidence.hard_gate_falsification_refs` is layered but each layer validates correctly.

4. **`control_allow_promotion` and `decision_blocked` are explicit final gates.** They cannot be bypassed through evidence manipulation.

5. **Promotion checks are ordered and deterministic.** No precedence ambiguity: the 8-step check sequence in `evaluate_sequence_transition` for `target_state == "promoted"` short-circuits on first failure and never continues through partially-failed state.

6. **`run_replay` (canonical path) is strongly hardened.** Requires full schema-valid inputs, non-placeholder trace_id, slo_definition, and enforces lineage validation. Blocked legacy replays cannot pass through `build_evaluation_control_decision` because they lack `observability_metrics`, `error_budget_status`, etc.

7. **The test `test_promotion_requires_replay_authority_refs_even_when_falsification_ref_can_be_resolved`** is a genuine regression test. It proves that even when falsification can be sourced from the cert_pack, the authority gate still requires direct `done_certification_input_refs` entries. This is correct.

---

### Weaknesses

**W1 — enforcement_result_ref is not required for promotion (immediate risk)**

`_promotion_authority_gate` only checks `enforcement_result_ref` if it is present in `done_certification_input_refs`. If the key is absent, enforcement evidence is not consumed at all.

```python
# sequence_transition_policy.py line 84
enforcement_ref = _ref_from_manifest(manifest, "enforcement_result_ref")
if enforcement_ref is not None:     # <-- only checked if declared
    ...
```

A cycle can be promoted with zero enforcement evidence. This is a direct trust-spine bypass path: omit `enforcement_result_ref` from `done_certification_input_refs` and the enforcement check is silently skipped.

**W2 — eval_coverage_summary_ref is not required for promotion (immediate risk)**

Same pattern as W1. If `eval_coverage_summary_ref` is absent from `done_certification_input_refs`, eval coverage is not consumed.

```python
# sequence_transition_policy.py line 93
coverage_ref = _ref_from_manifest(manifest, "eval_coverage_summary_ref")
if coverage_ref is not None:     # <-- only checked if declared
    ...
```

**W3 — policy_ref with no decision field silently allows promotion (medium risk)**

If `policy_ref` resolves to a readable JSON object that contains neither `decision` nor `system_response` fields, the resolution is:

```python
decision_value = str(policy_payload.get("decision") or policy_payload.get("system_response") or "").strip().lower()
# → ""
if decision_value in {"deny", "block", "freeze", "hold", "require_review"}:
    return False, ...
# Empty string is not in the set → passes
```

A policy artifact with no decision field passes the authority gate. This is fail-open on ambiguous authority.

**W4 — gate_proof_evidence in run_control_loop_certification.py is a shallow boolean flip (medium risk)**

`scripts/run_control_loop_certification.py` constructs gate_proof_evidence at lines 587–602:

```python
gate_proof_evidence = {
    "severity_linkage_complete": bool(gate_proof_refs),
    "deterministic_transition_consumption": bool(gate_proof_refs),
    "policy_caused_action_observed": bool(gate_proof_refs),
    ...  # all 9 booleans set to the same condition
    "severity_linkage_refs": list(gate_proof_refs),
    "transition_consumption_refs": list(gate_proof_refs),  # same refs for all
    "policy_action_refs": list(gate_proof_refs),
    ...
}
```

Passing a single `--gate-proof-ref` flag sets ALL 9 boolean fields to `True` and ALL 5 ref lists to the same single-file list. The certification pack's gate proof is semantically empty — it proves only that the caller passed a file path, not that each named requirement was independently evidenced.

When `_gate_proof_passes` in `sequence_transition_policy.py` consumes this pack, it accepts all 8 required fields as `True` and all 4 ref lists as non-empty. The gate passes on evidence that was never per-field verified.

**W5 — replay_result_ref presence check does not validate replay content (low-medium risk)**

`_promotion_authority_gate` checks `_path_exists(replay_ref)` — the file must exist and be a non-empty string. It does NOT read or validate the content. A blocked legacy replay result (status="blocked", prerequisites_valid=False, steps_executed=[]) at a valid path would satisfy this check. The promotion gate does not verify that the replay was successful or canonical.

---

### Hidden Risks

**HR1 — control_allow_promotion is never set by cycle_runner.py in three_slice mode**

In `cycle_runner.py`, when `sequence_mode == "three_slice"` and `state == "certification_pending"`, the `target_map` routes directly to `"promoted"` (line 520). The code calls `_authorize_sequence_transition("promoted")` which invokes `evaluate_sequence_transition`, which at line 260 requires `control_allow_promotion == True`.

But `cycle_runner.py` never sets `control_allow_promotion`. The `certification_pending` state handler at lines 916–972 only runs in the legacy path. In three_slice mode, all promotion authorization fields (`certification_status`, `control_allow_promotion`, `certification_record_path`) must be pre-set externally in the manifest.

This is a hidden assumption: the three_slice path expects an external orchestrator to have already stamped the manifest with authorization. There is no code that enforces this ordering. A future engineer could accidentally call `run_cycle()` with a three_slice manifest where `control_allow_promotion = True` and `certification_status = "passed"` are set without any actual certification having been run.

**HR2 — Inconsistent blocking vocabulary between enforcement and policy checks**

`policy_ref` blocks on `{"deny", "block", "freeze", "hold", "require_review"}`.
`enforcement_result_ref` blocks on `{"deny", "blocked", "freeze", "frozen", "require_review"}`.

The enforcement check uses `"blocked"` (not `"block"`) and `"frozen"` (not `"freeze"`), and does not check `"hold"`. If the enforcement result contains `final_status == "block"` or `"hold"`, it passes the enforcement gate. This vocabulary drift could allow future enforcement artifacts with non-canonical status strings to slip through.

**HR3 — Hard gate falsification fallback chain introduces indirect artifact resolution**

`_hard_gate_falsification_passes` has a multi-level fallback:
1. Inline `hard_gate_falsification` key in manifest
2. `hard_gate_falsification_record_path` in manifest
3. `done_certification_input_refs.hard_gate_falsification_record_path`
4. `certification_pack.gate_proof_evidence.hard_gate_falsification_refs[0]`

Level 4 involves resolving a file path embedded inside a file embedded inside a ref inside a dict. This chain is hard to audit, and a future refactor that changes where the falsification ref is stored could silently drop to a different fallback level without failing.

---

## Promotion Path Assessment

### Evidence Requirements

| Evidence | Required? | Content Validated? | Blocks on Bad Content? |
|---|---|---|---|
| `replay_result_ref` | YES — hard required | NO — only file existence | N/A |
| `policy_ref` | YES — hard required | YES — decision field checked | YES — but fails open if no decision field |
| `enforcement_result_ref` | NO — optional | YES — final_status checked | YES — only if declared |
| `eval_coverage_summary_ref` | NO — optional | YES — required_slice_gaps checked | YES — only if declared |
| `control_loop_gate_proof` | YES — all 8 bools required | Shallow — bools and ref lists | YES |
| `hard_gate_falsification` | YES — complex fallback | YES — artifact_type, result, checks | YES |

The two most dangerous columns are the "Required?" gaps for `enforcement_result_ref` and `eval_coverage_summary_ref`.

### Replay Dependency

`replay_result_ref` is required. Its file must exist. Its content is not validated. A blocked, partial, or legacy replay result at a valid path satisfies the promotion check. The canonical `run_replay` path is well-hardened but its output is not verified at the promotion gate.

### Enforcement Obedience

Enforcement evidence is consumed only if declared. When declared, it is meaningfully consumed (final_status evaluated). When absent, enforcement obedience is unproven. This is not fail-closed.

### Remaining Bypass Risk

The most exploitable bypass: omit `enforcement_result_ref` and `eval_coverage_summary_ref` from `done_certification_input_refs`. Both checks are silently skipped. No test asserts that their absence should block.

Secondary bypass: construct `policy_ref` as a JSON object with no `decision` or `system_response` field. The gate passes with empty-string decision.

---

## Test Coverage Assessment

**Covered and meaningful:**
- Hard gate falsification with `overall_result == "fail"` → blocks ✓
- Missing judgment artifact → blocks ✓
- Enforcement result with `final_status == "deny"` → blocks ✓
- Eval coverage with `required_slice_gaps` populated → blocks ✓
- Cert pack bypass attempt still requires direct replay_result_ref → blocks ✓
- `control_allow_promotion == false` → blocks ✓
- Missing failure binding proof field → blocks ✓

**Not covered — gaps that correspond directly to weaknesses:**

1. **Missing `enforcement_result_ref`**: No test asserts that omitting it from `done_certification_input_refs` blocks promotion. Currently it would not block — this needs a test AND a fix.

2. **Missing `eval_coverage_summary_ref`**: Same. No test, no block.

3. **Policy_ref with no decision field**: No test for a policy artifact where `decision` and `system_response` are both absent. Currently allows promotion.

4. **Replay_result_ref pointing to blocked/legacy content**: No test for a replay result file whose status is "blocked" or whose content is a legacy schema without observability fields.

5. **Gate proof with single file ref satisfying all boolean fields**: No test asserting that `severity_linkage_refs` and `policy_action_refs` must reference different, content-appropriate files.

6. **Contradictory evidence**: No test where `enforcement_result` says "deny" but `certification_status` is "passed" — tests only check the enforcement gate in isolation, not in combination with cert status.

7. **Stale/mismatched refs**: No test where `replay_result_ref` refers to a replay from a different cycle or with a mismatched trace_id.

8. **Three_slice path with manually pre-set control_allow_promotion**: No test that validates how `control_allow_promotion` gets set in three_slice mode and whether the certification step was actually executed.

The `indeterminate_paths.json` fixture covers only 2 cases (missing traceability, control_allow=false). It should be extended with at least 4 more ambiguity cases.

---

## Recommended Changes

### Must Do Now

**MN1: Require enforcement_result_ref for promotion**

Change `_promotion_authority_gate` so that `enforcement_result_ref` is not optional. If absent from `done_certification_input_refs`, return False with a blocking reason. This closes the most direct bypass path.

**MN2: Require eval_coverage_summary_ref for promotion**

Same change for coverage. Absence of coverage evidence should block, not silently proceed.

**MN3: Fail closed on policy_ref with no decision field**

In `_promotion_authority_gate`, after loading `policy_payload`, assert that at least one of `decision` or `system_response` is a non-empty string. If both are absent or empty, return False with reason "policy_ref artifact has no decision or system_response field". The current behavior (empty string not in blocking set → allow) is fail-open.

**MN4: Add regression tests for MN1–MN3**

- Test that promotion blocks when `enforcement_result_ref` is absent from `done_certification_input_refs`
- Test that promotion blocks when `eval_coverage_summary_ref` is absent
- Test that promotion blocks when `policy_ref` artifact has no `decision` or `system_response` field

### Should Do Soon

**SS1: Validate replay_result content at promotion gate**

Add a content check in `_promotion_authority_gate` for `replay_result_ref`: load the JSON and assert that `prerequisites_valid` is not False and `status` is not "blocked". A blocked replay result at a valid path should not satisfy the authority check.

**SS2: Align enforcement blocking vocabulary with policy blocking vocabulary**

The enforcement check blocks on `{"deny", "blocked", "freeze", "frozen", "require_review"}`. The policy check blocks on `{"deny", "block", "freeze", "hold", "require_review"}`. Unify to a shared blocking vocabulary constant that both checks consume. Add `"hold"` to the enforcement check. Consider `"block"` vs `"blocked"` normalization.

**SS3: Require independent per-field refs in gate_proof_evidence construction**

In `run_control_loop_certification.py`, the `gate_proof_evidence` construction must require separate, content-appropriate ref files for each ref list (`severity_linkage_refs`, `transition_consumption_refs`, `policy_action_refs`, `recurrence_prevention_refs`, `hard_gate_falsification_refs`). Currently all are set to the same single `gate_proof_refs` list. This doesn't need to be enforced at the schema level — just enforce it at the script level via distinct CLI flags.

**SS4: Document and test control_allow_promotion in three_slice mode**

The three_slice promotion path requires `control_allow_promotion == True` but never sets it. Document that this is an external orchestrator concern, add an explicit invariant check in `run_cycle()` that logs or warns when `sequence_mode == "three_slice"` and `control_allow_promotion` is not pre-set, and add a test that asserts the three_slice path blocks without it.

### Can Wait

**CW1: Flatten the hard gate falsification fallback chain**

The 4-level fallback in `_hard_gate_falsification_passes` works correctly but is hard to audit. Simplify by requiring either inline `hard_gate_falsification` OR a direct `done_certification_input_refs.hard_gate_falsification_record_path` — removing the cert_pack indirect chain as a standalone fallback. The cert_pack path is already covered by the gate_proof check; the falsification check should have its own clean path.

**CW2: Extend indeterminate_paths.json fixture**

Add at least 4 cases: missing enforcement_ref, missing coverage_ref, policy with no decision field, replay_result_ref pointing to blocked content.

---

## Suggested Follow-On Prompt

```
Task: Harden the promotion authority gate to require enforcement and coverage evidence.

Context:
- File: spectrum_systems/orchestration/sequence_transition_policy.py
- Function: _promotion_authority_gate (starts at line 67)
- Problem: enforcement_result_ref and eval_coverage_summary_ref are only checked when
  declared. Omitting them from done_certification_input_refs silently bypasses both checks.
  Additionally, policy_ref artifacts with no decision or system_response field currently
  pass the gate (empty string not in blocking set).

Changes required:
1. In _promotion_authority_gate, change the enforcement_result_ref check so it blocks if
   the ref is ABSENT from done_certification_input_refs:
     enforcement_ref = _ref_from_manifest(manifest, "enforcement_result_ref")
     if not _path_exists(enforcement_ref):
         return False, "promotion requires done_certification_input_refs.enforcement_result_ref"

2. Same change for eval_coverage_summary_ref.

3. After loading policy_payload, add a check:
     decision_value = str(policy_payload.get("decision") or policy_payload.get("system_response") or "").strip().lower()
     if not decision_value:
         return False, "policy_ref artifact has no decision or system_response field"

4. Add three regression tests in tests/test_sequence_transition_policy.py:
   - test_promotion_blocks_when_enforcement_result_ref_missing: use _base_manifest,
     remove enforcement_result_ref from done_certification_input_refs, assert blocks
     with "enforcement_result_ref" in reason
   - test_promotion_blocks_when_eval_coverage_summary_ref_missing: same pattern
   - test_promotion_blocks_when_policy_ref_has_no_decision_field: write a JSON file
     with no "decision" or "system_response" key, point policy_ref at it, assert blocks
     with "no decision" in reason

5. Update the indeterminate_paths.json fixture with these three cases.

Do not change any other promotion checks. Do not alter the schema. Do not add new
imports. Minimal-boundary changes only.
```

---

## Verdict

**ACCEPT WITH HARDENING**

RED-021 materially improved the promotion trust spine. The core gates are present and deterministic. The hard gate falsification check is structurally sound. The happy path test coverage is reasonable.

However, two medium-risk bypass paths remain open: enforcement evidence is not required (only checked if declared), and policy authority can silently pass when the policy artifact has no decision field. Additionally, the gate proof construction in the certification script is semantically hollow — it makes all boolean fields true from a single file reference.

These gaps are concrete and closable. The promotion path should not be considered trust-complete until MN1–MN4 are addressed. Subsequent capability should not be layered on top of this seam until it is closed.
