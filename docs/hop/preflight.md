# HOP authority-shape preflight

HOP is advisory-only. Release, promotion, rollback, certification,
control, enforcement, and judgment authority live with the canonical
owners (REL / CDE / SEL / TPA / GOV / JDG) per
`contracts/governance/authority_registry.json` and
`docs/architecture/system_registry.md`.

This page documents the local preflight contributors should run before
opening a PR that touches HOP files. The goal is to catch
authority-shaped residue (vocabulary, schema names, field shapes,
prompts) early so the fail-closed CI guards never have to.

The CI guards are unchanged. This page only adds local-developer
ergonomics — the same scripts already run inside CI's
`run_authority_leak_guard` and `run_system_registry_guard` steps.

## Quick reference

Run all three from the repo root before opening a PR:

```bash
python scripts/run_authority_shape_preflight.py \
    --base-ref origin/main --head-ref HEAD \
    --suggest-only \
    --output outputs/authority_shape_preflight/authority_shape_preflight_result.json

python scripts/run_system_registry_guard.py \
    --base-ref origin/main --head-ref HEAD \
    --output outputs/system_registry_guard/system_registry_guard_result.json

python scripts/run_authority_leak_guard.py \
    --base-ref origin/main --head-ref HEAD \
    --output outputs/authority_leak_guard/authority_leak_guard_result.json
```

If you have not pushed your branch yet (so `origin/main..HEAD` resolves
to an empty diff) or you are running before committing, pass an
explicit changed-file list instead:

```bash
CHANGED=$(git diff --name-only HEAD; git ls-files --others --exclude-standard)
python scripts/run_authority_shape_preflight.py --suggest-only \
    --changed-files $CHANGED \
    --output outputs/authority_shape_preflight/authority_shape_preflight_result.json
```

All three scripts emit a JSON artifact at `--output`; the leak and
registry guards exit non-zero on any violation. The shape preflight
defaults to `--suggest-only` (always exit 0) so you can iterate on a
work-in-progress branch without losing the run; pass `--strict` to
mirror the CI guard.

## What each script enforces

### `run_authority_shape_preflight.py` — advisory

- Runs the structural shape detector (`scripts/authority_shape_detector.py`)
  over each changed file and reports any object whose `artifact_type`
  or `schema_ref` matches `(decision|certification|promotion|enforcement)`
  outside a canonical owner path.
- Runs the forbidden-vocabulary scan and reports any forbidden field
  (`decision`, `enforcement_action`, `certification_status`,
  `certified`, `promoted`, `promotion_ready`) or value (`allow`,
  `block`, `freeze`, `promote`).
- Emits `text_hints[]` with suggested advisory-safe rewrites
  (e.g. `promotion_decision` → `release_readiness_signal`,
  `rollback_record` → `rollback_signal`,
  `quarantine` → `isolation_recommendation`,
  `block` → `risk_signal`). These are advisory only; you choose the
  term that best matches the local semantics.
- Default mode is `--suggest-only` (always exit 0); `--strict`
  exits non-zero on violations.

### `run_system_registry_guard.py` — fail-closed

- Cross-checks each changed file against `docs/architecture/system_registry.md`
  to catch shadow-ownership claims — for instance, the harness module
  appearing to claim an artifact already assigned to REL, CDE, PRG, or
  SEL.
- The guard's pattern list is in
  `spectrum_systems/modules/governance/system_registry_guard.py`
  (`_OWNER_CLAIM_PATTERNS`); current tokens include the obvious ones
  (`owns`, `owner of`, `canonical owner`) and several broader verbs.
- If a harness docstring or comment trips the guard, the fix is to
  name the canonical external owner explicitly and to drop the
  ownership-claim verb — for example,
  *"REL is the canonical release/rollback owner; the harness merely
  packages evidence."*

### `run_authority_leak_guard.py` — fail-closed

- The CI gate. Combines vocabulary scanning and structural shape
  detection. Failures here block PR promotion. Use the shape
  preflight to surface them before pushing.

## Authority-safe vocabulary cheat sheet

| Authority-shaped (avoid) | Advisory-safe (prefer) |
| --- | --- |
| `promotion_decision` | `release_readiness_signal` |
| `rollback_record` | `rollback_signal` |
| `control_decision` | `control_input` |
| `certification_record` | `evidence_packet` |
| `promote` | `advise_release` |
| `promoted` | `released_externally` |
| `promotion_ready` / `certified` | `readiness_signal` / `evidence_complete` |
| `allow` / `warn` / `block` / `freeze` | `ready_signal` / `warn_signal` / `risk_signal` |
| `rollback` | `restoration_signal` |
| `quarantine` | `isolation_recommendation` |
| `promotion gate` / `certification gate` | `release readiness check` / `advisory readiness check` |
| `control decision` | `control input` |

Use authority-shaped tokens *only* when the surrounding text names the
canonical external owner (REL / CDE / SEL / GOV / TPA / JDG). HOP
vocabulary should always describe a `signal`, `observation`, or
`evidence_packet` — never a verdict.

## When to run preflight

- Before pushing any branch that touches `contracts/evals/hop*`,
  `contracts/schemas/hop/`, `spectrum_systems/modules/hop/`,
  `tests/hop/`, or `docs/hop/`.
- Before bumping any HOP eval-set version.
- Before adding a new HOP artifact type or schema.
- After regenerating eval cases via
  `python contracts/evals/hop_heldout/generate_eval_set.py` or its
  search-set sibling.

## Where the guards live

- `scripts/authority_leak_rules.py` — vocabulary scanner.
- `scripts/authority_shape_detector.py` — structural shape detector.
- `scripts/run_authority_shape_preflight.py` — advisory wrapper for
  contributors (this page).
- `scripts/run_authority_leak_guard.py` — fail-closed CI gate.
- `scripts/run_system_registry_guard.py` — fail-closed CI gate.
- `contracts/governance/authority_registry.json` — registry of
  canonical owners and forbidden vocabulary.

If a guard surfaces a finding you believe is a false positive, *do not*
add an exception to the registry. Instead, rephrase the surrounding
text to name the canonical owner and remove the ownership-claim verb,
or rename the offending field/type to an advisory-safe form. Guard
weakening requires a governed registry update via the canonical owner.
