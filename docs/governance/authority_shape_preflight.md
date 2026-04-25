# Authority-Shape Preflight (AGS-001)

## Purpose

Catch authority-shaped terminology used by non-owner systems **before** full
CI, without weakening the system-registry guard or the authority-leak guard.
Recent HOP work repeatedly failed late CI because new files used names like
`promotion_decision`, `rollback_record`, or `enforcement_action` that belong to
canonical owners. The fail was correct — the loop was just slow. This preflight
moves the same enforcement earlier in the loop and adds suggested replacements
plus an opt-in safe-rename mode.

## Components

| Surface                                                              | Role                                            |
| -------------------------------------------------------------------- | ----------------------------------------------- |
| `contracts/governance/authority_shape_vocabulary.json`               | Reusable vocabulary map                         |
| `spectrum_systems/governance/authority_shape_preflight.py`           | Pure scanner + safe-rename library              |
| `scripts/run_authority_shape_preflight.py`                           | CLI gate with `suggest-only` and `apply` modes  |
| `tests/test_authority_shape_preflight.py`                            | Library tests                                   |
| `tests/test_run_authority_shape_preflight.py`                        | CLI tests                                       |

## What it checks

For each changed file inside `default_scope_prefixes` and not under
`excluded_path_prefixes`, the preflight:

1. Skips canonical-owner files for the relevant cluster (they are allowed to
   use the canonical term).
2. Skips guard scripts in `guard_path_prefixes` (they enumerate authority terms
   intentionally).
3. Walks every identifier on every line and flags any whose underscore-
   subtokens contain a cluster term **and** do not include a safety-suffix
   subtoken (`signal`, `observation`, `input`, `recommendation`, `finding`,
   `evidence`, `advisory`, `request`, ...).

For each violation the result includes:

- `file`, `line`, `symbol`
- `cluster` (e.g. `promotion`, `rollback`, `enforcement`)
- `canonical_owners` (the systems that may emit the term)
- `suggested_replacements` (advisory framings to use instead)
- `rationale`

## Vocabulary clusters

| Cluster        | Canonical owner(s) | Advisory replacements                                        |
| -------------- | ------------------ | ------------------------------------------------------------ |
| decision       | JDX, CDE           | signal, observation, recommendation, finding, input          |
| promotion      | REL, GOV, CDE      | promotion_signal, readiness_observation, promotion_input      |
| rollback       | REL                | rollback_signal, restoration_recommendation, rollback_input  |
| certification  | GOV, CDE           | certification_input, readiness_evidence, certification_signal|
| control        | CDE, TPA           | control_input, risk_signal, control_observation              |
| enforcement    | SEL, ENF           | enforcement_signal, compliance_observation, enforcement_input|
| approval       | GOV, HIT           | review_request, advisory_result, review_input                |
| release        | REL, GOV           | release_signal, release_input, release_observation           |
| authority      | GOV                | authority_input, authority_signal, authority_observation     |
| quarantine     | REL, SEC           | quarantine_signal, risk_observation, containment_recommendation |
| final          | CDE, GOV           | final_signal, final_observation, closure_input               |

## Modes

### `--suggest-only` (default)

Scan, report, fail-closed. No file mutations. Suitable for CI and pre-commit.

```bash
python scripts/run_authority_shape_preflight.py \
  --base-ref origin/main --head-ref HEAD --suggest-only
```

### `--apply-safe-renames`

Rewrites unambiguous, owner-safe text matches from
`safe_rename_pairs` (e.g. `promotion_decision` → `promotion_signal`,
`harness_rollback_record` → `harness_rollback_signal`,
`harness_routing_decision` → `harness_routing_observation`). Refuses to
modify:

- Guard scripts (`scripts/run_authority_*`, `spectrum_systems/modules/governance/system_registry_guard.py`, ...).
- Canonical-owner files (per the vocabulary's `owner_path_prefixes`).
- Files under `remediation_policy.rename_targets.exclude_path_prefixes`.

```bash
python scripts/run_authority_shape_preflight.py \
  --base-ref origin/main --head-ref HEAD --apply-safe-renames
```

After running with `--apply-safe-renames`, re-run with `--suggest-only` to
confirm the fix. The same preflight is the verifier for its own remediation.

## Example failure output

```
{
  "status": "fail",
  "mode": "suggest-only",
  "violation_count": 2,
  "first_violations": [
    {
      "file": "spectrum_systems/modules/hop/promotion_emitter.py",
      "line": 12,
      "symbol": "harness_promotion_decision",
      "cluster": "promotion",
      "canonical_owners": ["REL", "GOV", "CDE"],
      "suggested_replacements": ["promotion_signal", "readiness_observation",
                                  "promotion_input", "advancement_recommendation"]
    },
    {
      "file": "spectrum_systems/modules/hop/promotion_emitter.py",
      "line": 12,
      "symbol": "harness_promotion_decision",
      "cluster": "decision",
      "canonical_owners": ["JDX", "CDE"],
      "suggested_replacements": ["signal", "observation", "recommendation",
                                  "finding", "input"]
    }
  ]
}
```

## Integration

The preflight reuses
`spectrum_systems.modules.governance.changed_files.resolve_changed_files`, the
same fail-closed resolver used by `run_system_registry_guard.py` and
`run_authority_leak_guard.py`. Wire it as the first check in the same path so
violations are caught before the heavier guards run. The script returns a
non-zero exit code on any violation; CI must treat that as fail-closed.

## Design rules (do-not-do)

- Do not weaken existing guards.
- Do not add HOP-specific exceptions.
- Do not change canonical ownership.
- Do not suppress diagnostics.
- Do not make the preflight advisory-only in CI — the script's exit code is
  the gate.
