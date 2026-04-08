# Plan — BATCH-AEX-HARDEN-01 — 2026-04-08

## Prompt type
BUILD

## Roadmap item
BATCH-AEX-HARDEN-01 — Harden AEX enforcement, kill PQX bypass, complete traceability, and add drift tests

## Objective
Harden AEX/TLC/PQX repo-write boundaries so repo mutation cannot proceed without AEX admission artifacts, TLC-mediated lineage, and complete trace continuity.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-AEX-HARDEN-01-2026-04-08.md | CREATE | Plan-first requirement for multi-file hardening batch. |
| PLANS.md | MODIFY | Register the active hardening plan. |
| spectrum_systems/modules/runtime/repo_write_lineage_guard.py | CREATE | Single reusable fail-closed guard seam for repo-write admission/lineage validation. |
| spectrum_systems/modules/runtime/top_level_conductor.py | MODIFY | Enforce strict TLC repo-write admission guard and preserve AEX→TLC trace/lineage continuity into PQX handoff. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Block repo-write execution without AEX artifacts + TLC handoff lineage. |
| tests/test_tlc_requires_admission_for_repo_write.py | MODIFY | Add strict TLC failure and success cases for AEX artifact validation and trace continuity. |
| tests/test_pqx_repo_write_lineage_guard.py | CREATE | Prove PQX rejects repo-write execution without AEX/TLC lineage and accepts valid lineage. |
| tests/test_aex_repo_write_boundary_structural.py | CREATE | Structural drift tests including pragmatic scan for non-approved direct repo-write PQX invocation patterns. |
| docs/architecture/system_registry.md | MODIFY | Strengthen MUST-level boundary language and record TLC/PQX enforcement responsibilities. |
| docs/architecture/foundation_pqx_eval_control.md | MODIFY | Add concise fail-closed AEX→TLC→TPA→PQX enforcement-chain note. |

## Scope exclusions
- No new orchestration capabilities.
- No policy-engine expansion in AEX.
- No redesign of runtime execution model.

## Acceptance criteria
1. TLC rejects repo-write runs lacking valid AEX artifacts.
2. PQX sequence runner rejects repo-write runs lacking AEX/TLC lineage.
3. Repo-write lineage chain request→admission→orchestration→execution is reconstructable.
4. Structural drift tests lock boundary expectations.
5. Architecture docs reflect enforced behavior (not aspirational text).
