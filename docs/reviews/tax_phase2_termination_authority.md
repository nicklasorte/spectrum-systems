# CDE Phase 2 — Termination Authority

Implemented `spectrum_systems/modules/runtime/tax.py` with deterministic fail-closed termination functions:
- `build_termination_signals(...)`
- `compute_information_sufficiency(...)`
- `decide_termination(...)`
- `emit_termination_decision(...)`

Key controls:
- `complete` only when required artifacts/evals/trace/replay/policy/human-review and budget conditions are satisfied.
- Confidence is non-authoritative.
- Missing artifacts/evals/trace fail closed to block/freeze.

> Registry alignment note: see docs/architecture/system_registry.md.
