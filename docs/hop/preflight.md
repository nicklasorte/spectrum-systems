# HOP Authority-Shape Preflight

HOP is **advisory-only**. Release/restoration/advancement authority lives
with REL/GOV/CDE; enforcement lives with SEL. HOP files must not name
artifacts, fields, or enum values in shapes that imply HOP owns those
authorities. The AGS-001 preflight catches authority-shaped drift early.

## When to run

Before opening a PR that touches anything under:

- `spectrum_systems/modules/hop/`
- `spectrum_systems/cli/hop_cli.py`
- `contracts/schemas/hop/`
- `contracts/evals/hop/`, `contracts/evals/hop_heldout/`
- `docs/hop/`, `docs/reviews/hop_*.md`
- `scripts/hop_run_controlled_trial.py`
- `artifacts/hop_trial_run/`

The preflight is fast (stdlib-only) and runs locally without touching
the network.

## One-shot shortcut

```bash
bash scripts/preflight_hop.sh
```

This wraps the three guards required to ship a HOP change:

1. `scripts/run_authority_shape_preflight.py` — AGS-001 static scanner
   (suggest-only mode by default).
2. `scripts/run_system_registry_guard.py` — owner-claim guard.
3. `scripts/run_authority_leak_guard.py` — fail-closed leak detector.

The wrapper writes machine-readable results to `outputs/` so the same
artifacts can be inspected by hand or by CI.

## Manual commands

```bash
# AGS-001 authority-shape preflight (suggest-only)
python scripts/run_authority_shape_preflight.py \
    --base-ref origin/main \
    --head-ref HEAD \
    --suggest-only \
    --output outputs/authority_shape_preflight/authority_shape_preflight_result.json

# System-registry owner-claim guard
python scripts/run_system_registry_guard.py \
    --base-ref origin/main \
    --head-ref HEAD \
    --output outputs/system_registry_guard/system_registry_guard_result.json

# Authority-leak guard (forbidden vocabulary in non-owner paths)
python scripts/run_authority_leak_guard.py \
    --base-ref origin/main \
    --head-ref HEAD \
    --output outputs/authority_leak_guard/authority_leak_guard_result.json
```

Substitute `origin/main` with whatever base ref your branch diverges
from. CI uses the same flags.

## HOP-scoped pytest regression

A single pytest case enforces the same surface inside the HOP test
suite, so the violations cannot reach CI even if a contributor skips
the wrapper:

```bash
python -m pytest tests/hop/test_authority_shape_regression.py -q
```

## Repairing violations

The preflight emits a `suggested_replacement` for every flagged
identifier. Common renames:

| forbidden          | safe replacement           | owner            |
| ------------------ | -------------------------- | ---------------- |
| `promotion_decision` | `promotion_signal`       | REL / GOV / CDE  |
| `rollback_record`    | `rollback_signal`        | REL              |
| `control_decision`   | `control_input`          | CDE / TPA        |
| `certification_record` | `certification_input`  | GOV / CDE        |
| `release_decision`   | `release_signal`         | REL / GOV        |
| `quarantine_record`  | `quarantine_signal`      | REL / SEC        |
| `blocks_promotion`   | `release_block_signal`   | REL              |

Add the safe-suffix family (`_signal`, `_observation`, `_input`,
`_recommendation`, `_finding`, `_evidence`, `_advisory`, `_request`,
`_summary`) to any identifier that names an authority-flavoured noun.
The preflight skips identifiers that contain at least one safe-suffix
sub-token, so `release_block_signal` passes while `blocks_promotion`
fails.

## What the preflight will NOT catch

- Bare authority words inside English prose (titles, descriptions,
  comments) when they reference canonical owners by name. Where a
  reference is genuine, rephrase to use the owner's three-letter
  code (e.g. "REL is the canonical release owner"); the preflight
  treats `REL` as a non-cluster token.
- Test-data transcript content under `contracts/evals/`. The
  preflight scans these files because they ship as contract data, but
  test fixtures should still use authority-neutral synonyms so the
  data does not appear to assert authority on its own.

## Boundary

This preflight is a static scanner. It does **not** own runtime,
gating, or enforcement. The binding gate remains `scripts/run_authority_leak_guard.py`
in CI. The preflight only surfaces the same diagnostics earlier, with
suggested replacements, while the change is still local.
