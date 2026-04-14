# PYX-01 — Preflight Pytest Authority Hardening

## Problem statement
Governed contract preflight previously allowed architectural ambiguity between decision authority (preflight status/control signal) and execution authority (pytest runs in separate CI jobs). This could make PR trust signals appear stronger than preflight-owned execution truth.

## Root cause
1. Preflight and workflows both executed test-related logic, but only preflight should own PR gating execution truth.
2. Workflow topology allowed interpretation that downstream `run-pytest` evidence was equivalent to preflight execution evidence.
3. Trust-critical invariant language was not explicit enough about authority ownership boundaries.

## Before vs after authority model

### Before
- `run_contract_preflight.py` made allow/block decisions.
- Separate CI jobs could run pytest later.
- Authority seam was ambiguous: downstream pytest looked like gating evidence.

### After
- `run_contract_preflight.py` is the canonical owner of governed PR pytest execution truth.
- Preflight artifacts persist structured execution accounting (`pytest_execution`).
- PR allow/warn paths require preflight-owned execution count >= 1.
- Workflow checks explicitly validate preflight-owned execution accounting and fail closed on mismatch.
- `run-pytest` remains only a redundancy/health signal, not gating authority.

## Invariants
- `PR_PYTEST_EXECUTION_REQUIRED`
- `PR_PYTEST_FALLBACK_TARGETS_EMPTY`
- `PR_PYTEST_SELECTED_TARGETS_EMPTY` (selection reason code)
- `PREFLIGHT_PASS_WITHOUT_PYTEST_EXECUTION`

## Failure modes blocked
- PR allow/pass without any preflight-owned pytest execution.
- Empty targeted selection silently passing without governed fallback attempt.
- Empty fallback selection allowing ambiguous pass behavior.
- Workflow acceptance of allow/warn without preflight-owned execution accounting.

## Remaining risks
- Governance fallback target files can drift (rename/remove), which now fails closed (desired) and requires maintenance updates.
- Future workflow edits must preserve explicit authority comments and checks to avoid reintroducing trust seams.

## Recommended next follow-on step
Add a CI policy/lint check that enforces presence of workflow comments + trust-check script snippets where contract preflight jobs are defined, preventing accidental removal of authority-boundary checks.
