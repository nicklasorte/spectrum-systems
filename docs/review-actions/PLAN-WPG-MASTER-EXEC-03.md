# PLAN-WPG-MASTER-EXEC-03

Primary prompt type: BUILD

## Intent
Implement executable WPG hardening and surrounding governed workflow slices with deterministic schema-first artifacts, fail-closed control behavior, and regression validation.

## Execution slices
1. **Core hardening implementation (Phase A subset)**
   - Add missing WPG core schemas/examples for grounding, contradiction propagation, uncertainty control, and narrative integrity.
   - Wire deterministic artifact emission into WPG pipeline stages.
   - Enforce late-stage control-decision presence and fail-closed ingress behavior through governed pipeline checks.
2. **Red-team + mandatory fixes slice**
   - Expand WPG red-team suite and review outputs for core classes (conflict suppression, weak grounding, chronology distortion, missing control coverage).
   - Patch surfaced high-severity gaps and add regressions.
3. **Governance/review artifact slice**
   - Update required review documents and machine-readable findings artifacts for implemented slices.
4. **Validation slice**
   - Run focused WPG + contract enforcement commands; stop fail-closed if unmet gates remain.
5. **Delivery report slice**
   - Record completed code/tests/reviews, blocker boundaries, and certification posture.

## Stop conditions (fail-closed)
- Required schema/example artifact for implemented governed output missing.
- Required control decision missing on enforced WPG late-stage artifacts.
- High-severity red-team path still effectively ALLOW after fix slice.
