# Review Action Tracker: Budget-Aware Control-Loop Slice (SRE-09 / SRE-10)

- **Source Review:** `docs/reviews/2026-03-27-budget-control-loop-review.md`
- **Review ID:** 2026-03-27-budget-control-loop-review
- **Owner:** TBD
- **Last Updated:** 2026-03-27

---

## Critical Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
|---|---|---|---|---|---|
| BCL-CR-1 | Fix `_apply_budget_status_override` in `evaluation_control.py`: budget `warning` must NOT downgrade a pre-computed `deny` decision. Preserve `deny` + rationale code; only escalate from `allow`/`require_review` to `require_review`. Add test asserting `trust_breach + budget_warning → deny`. | TBD | Open | None | Critical fail-open condition. Target: implementation repo. Finding R-1. |
| BCL-CR-2 | Add budget-state-specific tests to chaos suite and CI gate: (a) warning over healthy → require_review; (b) warning over deny → deny unchanged; (c) exhausted → deny + gate blocks; (d) invalid → deny + gate blocks. Extend `align_replay_budget_with_observability` or add companion helper to recalculate `budget_status`. | TBD | Open | BCL-CR-1 | Required before any budget-aware CI gate behavior is considered tested. Target: implementation repo. Finding G-1, G-2. |

---

## High-Priority Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
|---|---|---|---|---|---|
| BCL-HI-1 | Add inverse consistency check to `_validate_replay_budget_inputs` in `control_loop.py`: raise `ControlLoopError` when `budget_status` severity exceeds `highest_severity`. | TBD | Open | None | Finding R-2, G-3. Target: implementation repo. |
| BCL-HI-2 | Replace partial structural checks in `_validate_replay_budget_inputs` with full schema delegation (`load_schema("error_budget_status")`). Layer cross-field guards on top. | TBD | Open | None | Finding R-3. Reduces schema drift risk. Target: implementation repo. |

---

## Medium-Priority Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
|---|---|---|---|---|---|
| BCL-MI-1 | Add `allOf` schema constraints to `evaluation_control_decision.schema.json` enforcing `decision=deny → system_response in (freeze, block)` and `decision=require_review → system_response=warn`. Optionally split `deny_budget_exhausted` rationale code into freeze and block variants. | TBD | Open | None | Finding R-4. Governance artifact — belongs in spectrum-systems. |

---

## Low-Priority Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
|---|---|---|---|---|---|
| BCL-LI-1 | Add `force_budget_invalid` path to `agent_golden_path.py` and golden-path test asserting `deny_budget_invalid` rationale. | TBD | Open | BCL-CR-1 resolved | Finding R-5. Target: implementation repo. |

---

## Blocking Items

- **BCL-CR-1** blocks trust in budget-warning governance for any downstream consumer. Any roadmap step that assumes budget warning escalates correctly is relying on broken behaviour.
- No other blocking items. BCL-CR-2 is required before budget-aware CI gate behavior is considered validated, but does not block unrelated work.

---

## Deferred Items

- **Schema rationale code precision (BCL-MI-1 extension)**: Splitting `deny_budget_exhausted` into `_freeze` and `_block` variants deferred until the operational distinction is confirmed as needed in the downstream enforcement model.
- **`budget_invalid` golden-path coverage (BCL-LI-1)**: Deferred until after critical and high items are resolved. Reopen trigger: before any operator-facing audit tooling consumes the golden-path output.

---

## Prioritized Backlog Order

1. BCL-CR-1 — fix warning downgrade (critical, unblocked)
2. BCL-CR-2 — budget-state test suite (critical, depends on CR-1)
3. BCL-HI-1 — inverse consistency check (high, unblocked)
4. BCL-HI-2 — schema delegation (high, unblocked)
5. BCL-MI-1 — schema decision/response constraints (medium, governance repo)
6. BCL-LI-1 — budget_invalid golden path (low, deferred)

---

## Follow-up Trigger Conditions

- When BCL-CR-1 and BCL-CR-2 are resolved: re-review budget-aware control semantics to confirm the warning path is now correct and test coverage is complete.
- Before any roadmap step introduces new budget states (e.g., "degraded"): re-run this review with expanded scope to catch new drift risks.
- Before any production-grade gating workflow is deployed: confirm BCL-CR-1 is resolved and BCL-CR-2 tests pass.
