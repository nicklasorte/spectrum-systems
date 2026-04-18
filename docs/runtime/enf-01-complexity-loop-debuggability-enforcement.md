# ENF-01 — Complexity, Loop-Alignment, and Debuggability Enforcement

## Prompt type
BUILD

## Intent
ENF-01 makes three engineering preconditions mandatory for new systems, major subsystem changes, and materially new control surfaces:

1. **Kill Complexity Early** via `complexity_justification_record`
2. **Build Fewer, Stronger Loops** via `core_loop_alignment_record`
3. **Optimize for Debuggability** via `debuggability_record`

This slice is additive and uses the existing EVL → control → enforcement path.

## Governed artifacts

### `complexity_justification_record`
Required evidence for why a subject exists and why an existing owner cannot cover it.

Fail-closed expectations:
- `failure_prevented` must be present.
- At least one measurable signal must be present (`measurable_metric` or `signal_improved`).
- `why_not_existing_owner` must be present.
- If `duplicate_of_system` is populated, progression is blocked unless the status is explicitly rejected/blocked.

### `core_loop_alignment_record`
Required evidence that the subject strengthens the canonical `execution → evaluation → control → enforcement` loop.

Fail-closed expectations:
- `maps_to_stages` must be non-empty.
- `strengthens_existing_loop` must be true or explicitly acceptable.
- `introduces_parallel_loop` must be false.
- `loop_impact_score` must be deterministic and bounded.

### `debuggability_record`
Required evidence that a new engineer can retrieve and diagnose failures.

Fail-closed expectations:
- `trace_complete` and `lineage_complete` must be true.
- `replay_supported` must be true when replay is expected.
- `failure_modes_defined` must be non-empty.
- `reason_codes_defined` must be true.
- `diagnostics_entrypoints` must identify where debugging starts.

## Required EVL evals

The required eval registry now declares these mandatory evals for `system_change_governance`:

- `complexity_justification_valid`
- `core_loop_alignment_valid`
- `debuggability_valid`

These are required eval artifacts, not advisory checks.

## Control + enforcement semantics

ENF-01 is consumed by the existing required-eval coverage enforcement seam.

### BLOCK
Progression is blocked when:
- Any of the three required artifact families are missing.
- Any of the required evals are missing or fail.
- Duplicate ownership signal is detected through complexity justification.
- Parallel loop introduction is detected.

### FREEZE
Progression is frozen when:
- Loop mapping is indeterminate.
- Debuggability evidence is incomplete but not definitively invalid.
- Replay/debug trace expectations are unclear.

### ALLOW
Progression is allowed only when:
- All three artifacts are present.
- All three required evals pass with deterministic evidence.
- No conflicting policy block/freeze condition is active.

## Runtime flow placement

ENF-01 artifacts and required eval outputs are consumed in:

1. EVL required eval registry mapping (`required_eval_registry`).
2. Required eval coverage enforcement (`missing_required_eval_enforcement`).
3. Control response mapping (`allow` / `freeze` / `block`) before progression.

This preserves artifact-first execution and fail-closed behavior without introducing a second enforcement model.
