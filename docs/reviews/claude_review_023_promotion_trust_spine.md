# Claude Review 023 — Promotion Trust Spine Review

## Scope Reviewed

Primary seam inspected:
- `spectrum_systems/orchestration/sequence_transition_policy.py`
- `spectrum_systems/modules/runtime/replay_engine.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/orchestration/cycle_runner.py`
- `scripts/run_control_loop_certification.py`

Primary trust-path tests and fixtures inspected:
- `tests/test_sequence_transition_policy.py`
- `tests/test_cycle_runner.py`
- `tests/test_replay_engine.py`
- `tests/test_control_loop_certification.py`
- `tests/fixtures/autonomous_cycle/*`
- `contracts/examples/control_loop_certification_pack.json`
- `contracts/examples/eval_coverage_summary.json`

Review posture: surgical trust-boundary review of promotion authority and evidence obedience only.

## What RED-021 Changed on the Promotion Path

RED-021 materially hardened promotion in the sequence path by introducing non-negotiable gates before `certification_pending -> promoted`:

- Promotion now requires both `done_certification_input_refs.replay_result_ref` and `done_certification_input_refs.policy_ref` to exist and be readable.
- Policy payload is consumed for blocking decisions (`deny/block/freeze/hold/require_review`).
- Optional `enforcement_result_ref` is consumed and can block promotion on deny-like final states.
- Optional `eval_coverage_summary_ref` is consumed and can block when `required_slice_gaps` is present/non-empty.
- Gate-proof evidence is now required and checked for required booleans and non-empty evidence refs.
- Hard-gate falsification evidence is required and must pass.
- Transition blocker precedence is now deterministic in implementation order (gate proof -> falsification -> promotion authority -> decision_blocked -> control_allow_promotion), and tests assert key precedence behavior.

Net: this closed the previous “promote with weak/no replay authority reference” hole on the main three-slice promotion edge.

## Architectural Judgment

**Judgment: fragile (improved but still bypassable through evidence-shape ambiguity and weak semantic binding).**

This is no longer the old open seam. It is meaningfully harder to promote without artifacts. But the spine still trusts artifact presence/readability more than artifact semantic consistency. That means fail-closed exists for some missing refs, but not for conflicting or stale authority in several high-risk scenarios.

## Findings

### Strengths

- Promotion cannot proceed in three-slice mode without explicit replay and policy refs.
- Promotion blocks on deny-like policy decisions and deny-like enforcement status when provided.
- Promotion blocks if gate-proof booleans/evidence refs are incomplete.
- Promotion blocks if hard-gate falsification is missing, malformed, wrong type, failed, or incomplete.
- Replay engine canonical path is explicitly enforced and legacy enforcement path is guarded by tests.
- Sequence/cycle tests include key regression checks for missing replay authority refs and blocker precedence.

### Weaknesses

1. **Eval coverage check is schema-fragile and effectively optional in practice.**
   The promotion gate checks `required_slice_gaps`, but the canonical example uses `coverage_gaps` / `uncovered_required_slices`. A real coverage artifact can indicate serious coverage holes and still not block promotion if `required_slice_gaps` is absent.

2. **`enforcement_result_ref` and `eval_coverage_summary_ref` are treated as optional despite being on the trust spine request.**
   If omitted, promotion still proceeds. That is not “evidence-bound by default”; it is “evidence-bound only when supplied.”

3. **Replay artifact is required by path existence only; semantic lineage is not consumed at promotion boundary.**
   Promotion does not verify replay artifact schema, trace/cycle linkage, or correspondence to `policy_ref` / certification context.

4. **Policy authority is consumed shallowly.**
   Gate reads decision text but does not validate decision schema nor verify linkage (trace/run/input signal) to the replay artifact or cycle.

5. **Certification-pack gate-proof refs are only non-empty checks.**
   No existence/readability or content verification for those referenced evidence paths at promotion time.

### Hidden Risks

- **Promotion-by-stale-reference risk:** old but readable allow policy + unrelated replay path can satisfy current checks.
- **Promotion-by-coverage-key mismatch risk:** coverage artifact can report required-slice deficit without `required_slice_gaps`, and promotion passes.
- **Future refactor regression risk:** because authority checks are spread and mostly shallow, a small schema/key drift can silently weaken blocking behavior.

## Promotion Path Assessment

### Evidence Requirements

Current state:
- Strictly required: `replay_result_ref`, `policy_ref`, certification status/record, gate proof, hard-gate falsification, `control_allow_promotion=true`.
- Conditionally enforced only when declared: `enforcement_result_ref`, `eval_coverage_summary_ref`.

Assessment:
- Better than pre-RED-021, but still not fully evidence-bound because two requested authority artifacts remain optional and not mandatory for promotion.

### Replay Dependency

- Replay ref is now mandatory for promotion edge and tested.
- Replay bypass via legacy replay engine path is well-defended at runtime replay layer.
- **But promotion boundary does not validate replay artifact semantics** (schema, linkage, canonicality markers, cycle/trace binding). So replay is required as a file, not fully as authoritative evidence.

### Enforcement Obedience

- If `enforcement_result_ref` is present, deny-like statuses block promotion.
- This is behaviorally meaningful, not mere existence check.
- But because ref is optional and linkage to policy/replay is not verified, obedience is incomplete.

### Remaining Bypass Risk

- **Yes, still bypassable** under crafted but readable stale/mismatched authority artifacts.
- The seam is fail-closed for missing required refs, but not fail-closed for cross-artifact inconsistency.

## Test Coverage Assessment

Good coverage present for:
- missing replay authority ref at promotion
- hard-gate falsification failures
- enforcement deny blocking (when provided)
- eval coverage gap blocking (for `required_slice_gaps` key)
- blocker precedence (`replay_result_ref`/hard-gate path before `control_allow_promotion`)

Missing high-value regressions:
1. **Coverage schema-key drift test:** coverage artifact with `coverage_gaps` / `uncovered_required_slices` should block if required-slice gaps exist.
2. **Unreadable/invalid replay artifact test at promotion boundary:** existing path check is insufficient.
3. **Unreadable/invalid policy artifact schema test with contradictory fields (`decision=allow`, `system_response=block`) and explicit precedence expectation.**
4. **Mismatched linkage tests:** replay trace/run/id not matching policy/enforcement/cycle context should block.
5. **Stale authority test:** old timestamped policy/replay refs incompatible with current cycle should block.
6. **Omitted enforcement/eval coverage refs test asserting fail-closed requirement (if policy is to require them).**

## Recommended Changes

### Must Do Now

1. **Make promotion consume eval coverage semantically, not by one fragile key.**
   In `sequence_transition_policy`, block promotion when coverage indicates required-slice holes via any canonical field (`required_slice_gaps`, `coverage_gaps` severity+required, `uncovered_required_slices`).

2. **Require and validate `enforcement_result_ref` and `eval_coverage_summary_ref` on promotion spine.**
   Do not leave these as optional if they are part of required authority surface.

3. **Add semantic linkage checks between replay/policy/enforcement artifacts at promotion time** (at least trace_id and source artifact linkage).

### Should Do Soon

1. Validate `policy_ref` against `evaluation_control_decision` schema at promotion gate.
2. Validate `replay_result_ref` against replay schema at promotion gate.
3. Verify gate-proof evidence refs exist/read and are not just non-empty strings.

### Can Wait

1. Refactor authority-gate logic into a single typed validator object to reduce future precedence drift.
2. Add explicit anti-staleness policy fields (e.g., max age / same-cycle token) if lifecycle policy requires freshness bounds.

## Suggested Follow-On Prompt

```text
# BUILD — RED-023A Promotion Coverage + Authority Binding Hardening

Harden only the promotion authority gate in:
- spectrum_systems/orchestration/sequence_transition_policy.py
- tests/test_sequence_transition_policy.py
- tests/test_cycle_runner.py (only if needed for sequence-mode integration assertions)

Objective:
Make promotion fail-closed when eval coverage evidence is present but expressed through canonical non-`required_slice_gaps` fields, and remove optionality for enforcement/coverage refs on promotion trust spine.

Required implementation:
1) In `_promotion_authority_gate`, require these refs in `done_certification_input_refs`:
   - replay_result_ref
   - policy_ref
   - enforcement_result_ref
   - eval_coverage_summary_ref
2) Keep existing deny/block semantics for policy and enforcement.
3) Expand eval coverage blocking logic so promotion blocks when any of the following indicate required-slice deficit:
   - non-empty `required_slice_gaps`
   - non-empty `uncovered_required_slices`
   - `coverage_gaps` contains entries that indicate required coverage is missing (treat severity high/critical as blocking)
4) Add deterministic tests that fail before and pass after:
   - missing enforcement_result_ref blocks
   - missing eval_coverage_summary_ref blocks
   - coverage artifact with `uncovered_required_slices` blocks
   - coverage artifact with `coverage_gaps` high-severity required-slice missing blocks
5) Do not modify unrelated modules.

Validation:
- Run `pytest tests/test_sequence_transition_policy.py -q`
- Run `pytest tests/test_cycle_runner.py -q`

Deliverable:
Commit with a focused message describing promotion fail-closed hardening for enforcement+coverage authority.
```

## Verdict

**ACCEPT WITH HARDENING**

RED-021 fixed the immediate replay-authority hole and materially improved fail-closed behavior. But promotion is not yet fully trustworthy under artifact ambiguity or stale/mismatched authority. One surgical hardening slice is still required before building more capability on this spine.
