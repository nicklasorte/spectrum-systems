# PLAN-PRA-NSX-PRG-001-HARDENING-001-AUTHORITY-SHAPE-FIX-2026-04-18

Primary Prompt Type: BUILD

## Intent
Apply a surgical authority-shape artifact-type repair for PR #1107 by identifying the exact remaining offender and renaming only that artifact type to a non-authoritative shape.

## Method
1. Reproduce authority leak failure and inspect guard output artifact for exact offending `artifact_type`.
2. Confirm trigger logic in `scripts/run_authority_leak_guard.py` and `scripts/authority_shape_detector.py`.
3. Rename only the offending artifact type token and linked references across example, schema const, manifest, runtime, and tests.
4. Avoid guard weakening and avoid broad PRA/NSX/PRG redesign.
5. Re-run validation sequence and update delivery report.

## Guardrails
- No changes to guard detection logic.
- No speculative governance expansion.
- Keep PRA/NSX/PRG advisory/extractive/generative.
- Minimal diff for the single remaining `authority_shape_artifact_type` failure.
