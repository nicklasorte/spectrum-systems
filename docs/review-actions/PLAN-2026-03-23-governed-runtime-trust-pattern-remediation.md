# PLAN — 2026-03-23 Governed Runtime Trust-Pattern Remediation

## Objective
Eliminate trust-breaking implementation patterns identified in the 2026-03-23 governed runtime audit, with strict focus on fail-closed behavior, deterministic identity, canonical contracts, replay trust, and observability correlation integrity.

## Entry Criteria
- Review artifact approved for remediation: `docs/reviews/2026-03-23-governed-runtime-trust-pattern-audit.md`.
- Scope frozen to audited runtime/control-loop surfaces (no architecture redesign).
- Contract owners and runtime owners aligned on canonical artifact boundaries.

## Ranked Remediation Queue
1. **CR-1 (P1):** Canonicalize `validator_execution_result` output shape and enforce schema in all branches.
2. **CR-2 (P1):** Remove canonical+legacy dual acceptance from governed replay validation path.
3. **CR-3 (P1):** Introduce deterministic identity strategy for governed enforcement/control references.
4. **HI-1 (P2):** Enforce strict correlation keys for `control_execution_result` and trace attachments.
5. **HI-2 (P2):** Remove silent fallback/time-seeded identity in run-bundle validation decision path.
6. **MI-1 (P3):** Require explicit replay linkage IDs in replay governance boundary.

## Fix Slices by Order

### Slice 1 — Validator artifact shape integrity (CR-1)
- Target:
  - `spectrum_systems/modules/runtime/validator_engine.py`
  - `contracts/schemas/validator_execution_result.schema.json`
  - `tests/test_validator_engine.py`
- Change intent:
  - Single canonical `validator_execution_result` shape for all code paths.
  - No early-return branch that bypasses final schema enforcement.
  - Explicit correlation keys standardized and schema-governed.

### Slice 2 — Replay canonical contract enforcement (CR-2)
- Target:
  - `spectrum_systems/modules/runtime/replay_engine.py`
  - `tests/test_replay_engine.py`
- Change intent:
  - Governed BAG path validates canonical replay schema only.
  - Legacy shape support moved to explicitly named legacy adapter/validator path.

### Slice 3 — Deterministic governed identity hardening (CR-3)
- Target:
  - `spectrum_systems/modules/runtime/enforcement_engine.py`
  - `spectrum_systems/modules/runtime/control_loop.py`
  - `contracts/schemas/enforcement_result.schema.json` (if needed for deterministic ID format constraints)
  - `tests/test_enforcement_engine.py`
  - `tests/test_replay_engine.py`
- Change intent:
  - Replay-critical artifact references derive from stable canonical inputs.
  - Wall-clock/random values retained only as metadata, not identity anchors.

### Slice 4 — Control execution correlation integrity (HI-1)
- Target:
  - `spectrum_systems/modules/runtime/control_executor.py`
  - `contracts/schemas/control_execution_result.schema.json`
  - `tests/test_control_executor.py`
- Change intent:
  - Forbid placeholder correlation IDs in governed emissions.
  - Ensure attached artifact ID uniquely represents emitted execution artifact.

### Slice 5 — Run-bundle validator fail-closed + deterministic decision IDs (HI-2)
- Target:
  - `spectrum_systems/modules/runtime/run_bundle_validator.py`
  - `tests/test_run_bundle_validator.py`
- Change intent:
  - Trace runtime unavailability blocks emission (no random fallback).
  - Decision ID derived from deterministic canonical report content (no timestamp seed).

### Slice 6 — Replay governance explicit linkage boundary (MI-1)
- Target:
  - `spectrum_systems/modules/runtime/replay_governance.py`
  - relevant governance tests
- Change intent:
  - Explicit `trace_id`/`replay_run_id` required at governed boundary.
  - Auto-extraction retained only behind explicit legacy/deprecation adapter.

## Validation Required for Each Fix
For each slice:
1. **Unit + contract tests** for affected modules pass.
2. **Negative tests** confirm fail-closed behavior for missing/placeholder correlation keys.
3. **Determinism checks** verify stable IDs for identical governed inputs.
4. **No dual-shape acceptance** tests for governed paths.
5. **Changed-scope verification** confirms only planned files changed.

## Exit Criteria Before Roadmap Advancement
- All CR/HI remediation slices complete and merged.
- Canonical governed replay + validator outputs have single, schema-enforced shape.
- Deterministic identity tests passing for enforcement/replay linkage surfaces.
- No placeholder/default correlation keys accepted in governed artifact emissions.
- No silent fallback behavior in reviewed trust boundaries.
- Updated review closure artifact records evidence and residual risk status as acceptable.
