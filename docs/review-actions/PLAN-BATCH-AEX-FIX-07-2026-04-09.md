# PLAN-BATCH-AEX-FIX-07-2026-04-09

## Prompt Type
BUILD

## Scope
Harden three trust-boundary issues without architecture redesign:
1. Narrow authoritative lineage signing to AEX/TLC boundary emission paths.
2. Persist replay-token consumption so repo-write lineage replay is rejected across process boundaries.
3. Enforce canonical/symlink-safe repo path detection for lineage requirement decisions.

## Steps
1. Update lineage authenticity issuance API to enforce boundary-owned caller controls and keep verification unchanged.
2. Rewire AEX/TLC emission paths to use boundary-specific issuance wrappers; remove non-authoritative direct issuance usage.
3. Replace in-memory-only replay token set with deterministic persistent registry scoped to repo runtime state.
4. Harden PQX repo-controlled path checks to canonical resolved paths with fail-closed behavior on ambiguity.
5. Add adversarial regression tests for non-authoritative minting, cross-process replay rejection, and symlink path bypass closure.
6. Run targeted tests for lineage guard, PQX slice runner, TLC/AEX flows, and cycle runner readiness paths.
7. Update minimal architecture note documenting issuance restriction, persistent replay, and canonical path enforcement.
