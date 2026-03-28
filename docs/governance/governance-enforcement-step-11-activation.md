# Step 11 — Activate Governance Enforcement Roadmap

- **Date:** 2026-03-28
- **Status:** ACTIVE (documentation + structure activation)
- **Execution boundary:** Governance documentation only (no runtime, schema, or certification code changes)
- **Authority:** `docs/roadmaps/system_roadmap.md` (ACTIVE roadmap)

## Objective

Activate Step 11 governance enforcement as an operational documentation surface that defines enforceable governance rules, activation criteria, and deterministic evidence requirements for parallel PQX work.

## Enforcement rules (Step 11 activation)

1. **Roadmap authority rule**
   - Implementation decisions must trace to `docs/roadmaps/system_roadmap.md`.
   - Non-authoritative roadmap files are context-only.

2. **Plan-before-build rule**
   - Any change exceeding two files must include a written plan in `docs/review-actions/` before BUILD/WIRE execution.

3. **Declared-scope rule**
   - Every slice must declare an explicit file list.
   - Changes outside declared scope require explicit documented justification before merge.

4. **Isolation rule for parallel slices**
   - Parallel slices must not overlap on files.
   - Parallel slices must not share mutable control assumptions (schemas, manifests, certification or control-loop logic).

5. **Validation rule**
   - Each slice must pass required tests independently before merge.
   - Post-merge targeted checks must confirm certification/promotion behavior is unchanged.

6. **Deterministic evidence rule**
   - Action tracker entries must capture baseline commit, branch names, diff evidence, merge order, and post-merge results.

## Activation criteria

Step 11 is considered **activated** when all criteria below are satisfied for the running execution item:

- A plan artifact exists and declares exact changed files.
- Two branches are created from the same baseline commit.
- Each branch demonstrates non-overlapping, independently validated scope.
- Cross-diff inspection confirms no file and semantic overlap.
- Merge sequence is executed in risk order with documented rationale.
- Post-merge certification/promotion-targeted checks pass with deterministic attribution.
- Action tracker records closure decision and isolation outcome.

## Out of scope

- Runtime logic changes.
- Certification gate code changes.
- Enforcement bridge behavior changes.
- Shared schema, manifest, or contract updates.

## Evidence hooks for this activation

- `docs/review-actions/2026-03-28-pqx-clt-012-parallel-trial-actions.md`
- `docs/reviews/2026-03-27-parallel-pqx-trial-closure.md`
