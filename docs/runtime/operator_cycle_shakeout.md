# Operator System Cycle Shakeout (BATCH-Y)

This is the recommended operator flow for exercising the governed system in realistic usage and harvesting the next hardening backlog.

## Purpose

Run deterministic scenarios through the existing operator seam (`run_system_cycle`) and emit two governed artifacts:

- `operator_friction_report`
- `operator_backlog_handoff`

These artifacts answer:

1. What was hard/noisy in real operator usage?
2. Where manual interpretation is still required?
3. What small, highest-value hardening work should run next?

## Command

```bash
python scripts/run_operator_shakeout.py \
  --pqx-state-path tests/fixtures/pqx_runs/state.json \
  --pqx-runs-root tests/fixtures/pqx_runs \
  --output-dir runs/operator_shakeout \
  --created-at 2026-04-03T23:59:00Z
```

Optional:

- `--scenario-id SCN-HAPPY_PATH_BOUNDED` (repeatable flag) to run a bounded subset.

## What runs

The shakeout executes deterministic scenarios covering:

- happy-path bounded cycle
- stop on missing required review propagation
- stop on program-constraint misalignment
- stop on repeated TPA risk
- complete-and-recommend-next-step path
- noisy/confusing failure surface path
- weak recommendation/trace discoverability path

## Artifacts and interpretation

### `operator_friction_report`

For each scenario, read:

- `friction_type`
- `severity`
- `stop_reason`
- `blockers`
- `outcome_understandable`
- `next_action_obvious`
- `manual_interpretation_required`

If `manual_interpretation_required=true`, treat it as immediate usability debt even when fail-closed behavior is correct.

### `operator_backlog_handoff`

Use `prioritized_items` as rack-and-stack input for the next implementation batch.

Priority is designed for:

1. highest operator time saved,
2. highest trust gain,
3. smallest coherent changes,
4. lowest architecture risk.

## Stop-condition interpretation (today)

When reading per-scenario `build_summary.failure_surface.stop_reason`:

- `max_batches_reached`: normal bounded stop; continue with next governed cycle.
- `authorization_block` / `authorization_freeze`: gate state unresolved; collect required evidence/reviews.
- `missing_required_signal`: intake/setup gap; patch operator inputs and rerun.
- `execution_blocked`: execution seam blocked; inspect blockers + run artifacts before rerun.
- `no_eligible_batch`: roadmap readiness/selection gap; refresh roadmap artifact.

## Operator next-step checklist

1. Open `operator_friction_report` and isolate `severity=high` friction first.
2. Confirm each high-friction entry has clear `artifact_refs` and deterministic root-cause hypothesis.
3. Open `operator_backlog_handoff` and execute ranked items in order unless a dependency note requires reorder.
4. Keep BATCH-Z fail-closed authority boundaries unchanged while applying BATCH-U usability hardening.
