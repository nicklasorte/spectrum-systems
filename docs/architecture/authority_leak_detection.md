# Authority Leak Detection Layer

## Definition
An **authority leak** is any non-canonical surface that emits authority vocabulary or produces an authority-shaped artifact that can be interpreted as control, enforcement, certification, or promotion authority.

This layer enforces fail-closed boundaries aligned to canonical ownership from `docs/architecture/system_registry.md`.

## Canonical authority owners
Machine-readable owner mapping is defined in:
- `contracts/governance/authority_registry.json`

Categories covered:
- `control_decision`
- `enforcement`
- `certification`
- `promotion`

Only declared canonical owners for each category may emit authority artifacts or authority vocabulary.

## Forbidden vocabulary boundary
Guard rules are defined in:
- `scripts/authority_leak_rules.py`

Forbidden fields outside canonical owners:
- `decision`
- `enforcement_action`
- `certification_status`
- `certified`
- `promoted`
- `promotion_ready`

Forbidden values outside canonical owners:
- `allow`
- `block`
- `freeze`
- `promote`

Overrides are only allowed when explicitly declared in `authority_registry.json`.

## Authority-shape detection
Structural detection is implemented in:
- `scripts/authority_shape_detector.py`

The detector blocks non-owner artifacts that:
- combine outcome + action semantics in one object,
- resemble certification/promotion verdict artifacts,
- advertise authority-shaped `artifact_type` or `schema_ref`,
- declare preparatory assertions but still carry authority semantics.

## Preparatory-only convention
Preparatory artifacts are observational only.

Required field:
```json
"non_authority_assertions": [
  "preparatory_only",
  "not_control_authority",
  "not_certification_authority"
]
```

Allowed preparatory fields:
- `observations`
- `counts`
- `refs`
- `replay_hash`
- `trace_refs`
- `non_authority_assertions`

Preparatory artifacts must not include final-state authority fields or authority verdict values.

## CI/guard enforcement
Runner:
- `scripts/run_authority_leak_guard.py`

Behavior:
1. Load `contracts/governance/authority_registry.json`.
2. Resolve changed files (`--changed-files` or git diff base/head).
3. Apply forbidden vocabulary and authority-shape detection.
4. Emit JSON artifact at `outputs/authority_leak_guard/authority_leak_guard_result.json`.
5. Exit non-zero on any violation.

## Developer compliance
When adding/modifying artifacts:
1. Keep decision/enforcement/certification/promotion semantics within canonical owners.
2. Use preparatory artifacts for observational outputs only.
3. Include required `non_authority_assertions` for preparatory artifacts.
4. Run `python scripts/run_authority_leak_guard.py --changed-files ...` before commit.
