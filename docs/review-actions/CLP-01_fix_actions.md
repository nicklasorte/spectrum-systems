# CLP-01 Fix Actions (Prompt type: BUILD)

## AEX admission step
- request type and intended outcome: BUILD; add Core Loop Pre-PR Gate artifact + runner + integration/tests to catch AGL-01 failure classes pre-PR.
- changed surfaces: `contracts/schemas/`, `contracts/examples/`, `contracts/standards-manifest.json`, `scripts/`, `spectrum_systems/modules/runtime/`, `tests/`, `docs/reviews/`, `docs/review-actions/`.
- authority-shape risks: avoid introducing new owner claims; keep `authority_scope` pinned to `observation_only`; map evidence to canonical owners from `docs/architecture/system_registry.md`.
- required tests/eval coverage: `tests/test_core_loop_pre_pr_gate.py`, `tests/test_agent_core_loop_proof.py`, contract enforcement and authority guards.
- required schema/artifact updates: add `core_loop_pre_pr_gate_result` schema/example + standards manifest registration.
- required governance mappings: wire missing CLP evidence into AGL proof evaluation for repo-mutating work.
- replay/observability updates: include `trace_refs` and `replay_refs` in emitted gate artifact.
- scope split check: admissible as one governed slice.

## Must-fix findings and dispositions
- disposition: fixed in this PR (filled after implementation below).
