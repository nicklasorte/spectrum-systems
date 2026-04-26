# TLS Priority Preflight (TLS-GUARD-01)

Local fast-feedback wrapper for the authority checks that gate TLS
dependency-priority and 3LS dashboard changes. The wrapper does **not** own
gating — the binding gate remains `scripts/run_authority_leak_guard.py` in CI.
It only surfaces the same diagnostics earlier so contributors do not push,
fail CI, then re-run locally.

## When to run it

Before opening a PR that touches anything under:

- `scripts/build_tls_dependency_priority.py`
- `spectrum_systems/modules/tls_dependency_graph/`
- `tests/tls_dependency_graph/`
- `artifacts/tls/`
- `artifacts/system_dependency_priority_report.json`
- `apps/dashboard-3ls/` (especially `app/api/priority/`,
  `app/api/intelligence/`, `lib/artifactLoader.ts`, `app/page.tsx`)
- `contracts/governance/authority_shape_vocabulary.json` when the change
  touches a TLS observer cluster

One-shot:

```bash
bash scripts/preflight_tls_priority.sh
```

Configure refs and candidates via environment:

```bash
BASE_REF=origin/main HEAD_REF=HEAD \
CANDIDATES=H01,RFX,HOP,MET,METS \
bash scripts/preflight_tls_priority.sh
```

## What each guard protects

| Step | Guard | What it protects |
| ---- | ----- | ---------------- |
| 1 | `scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS` | The five-phase TLS pipeline (graph → evidence → classification → trust gaps → ranking). Fails closed on any phase that cannot produce a schema-valid artifact, so a broken priority report never reaches the dashboard. |
| 2 | `scripts/run_authority_shape_preflight.py --suggest-only` | AGS-001 static identifier scanner. Flags symbols in changed files that resemble owner-cluster terms (`*_decision`, `*_promotion`, `*_certification`, `*_enforcement`, …) and suggests safe observer-flavoured replacements. Suggest-only mode is non-mutating but still fails closed when leaks are present. |
| 3 | `scripts/run_authority_leak_guard.py` | Fail-closed authority-leak detector. The binding CI gate. Catches any forbidden authority vocabulary that the shape preflight surfaced as well as legacy patterns the static scanner does not enumerate. |
| 4 | `pytest tests/tls_dependency_graph` | Phase-by-phase regression suite for the TLS dependency graph. Guards the deterministic ranking contract and the schema bindings the dashboard relies on. |

If `git diff --name-only` shows changes under any dashboard surface
(`apps/dashboard-3ls/`, `apps/dashboard/`, `app/dashboard/`,
`app/dashboard-3ls/`, `components/dashboard/`, `src/dashboard/`,
`spectrum_systems/dashboard/`), the wrapper prints:

```
Run dashboard-3ls tests before pushing.
```

Run them with:

```bash
cd apps/dashboard-3ls && npm test
```

The wrapper does not invoke the dashboard suite itself because the JS
toolchain is not assumed to be present in every contributor environment;
the reminder keeps the gate explicit without weakening it.

## Forbidden vocabulary and safe replacements

TLS modules are observers — they produce signals, observations, and
recommendations that owner-cluster systems interpret. Owner declarations
live in `docs/architecture/system_registry.md` and
`contracts/governance/authority_shape_vocabulary.json`; reference those
files for the binding owner table. The table below pairs each forbidden
identifier with a safe observer-vocabulary replacement.

| forbidden                 | safe replacement                | owner            |
| ------------------------- | ------------------------------- | ---------------- |
| `promotion_decision`      | `promotion_signal`              | CDE / GOV / REL  |
| `rollback_record`         | `rollback_signal`               | REL              |
| `control_decision`        | `control_input`                 | CDE / TPA        |
| `certification_record`    | `certification_input`           | GOV / CDE        |
| `enforcement_action`      | `enforcement_signal`            | SEL / ENF        |
| `release_decision`        | `release_signal`                | REL / GOV        |
| `quarantine_record`       | `quarantine_signal`             | REL / SEC        |
| `final_verdict`           | `final_signal`                  | CDE / GOV        |
| `approval_authority`      | `review_request`                | GOV / HIT        |
| `authoritative_record`    | `authority_signal`              | GOV              |
| `blocks_promotion`        | `release_block_signal`          | REL              |
| `advancement_decision`    | `advancement_signal`            | CDE / GOV        |

Use the safe-suffix family on any identifier that names an owner-cluster
noun: `_signal`, `_observation`, `_input`, `_recommendation`, `_finding`,
`_evidence`, `_advisory`, `_request`, `_summary`. The shape preflight
skips identifiers that contain at least one safe-suffix sub-token, so
`release_block_signal` passes while `blocks_promotion` fails.

## Boundary

This wrapper is a static, non-owning preflight. It does **not**:

- own runtime, gating, or enforcement;
- replace the CI authority-leak guard;
- weaken any guard — every step uses the same flags CI uses;
- mutate governed artifacts (it runs `--suggest-only` for the shape preflight).

The binding gate is `scripts/run_authority_leak_guard.py` in CI. The
wrapper only surfaces the same diagnostics earlier, with suggested
observer-safe replacements, while the change is still local.

## References

- `scripts/preflight_tls_priority.sh`
- `scripts/build_tls_dependency_priority.py`
- `scripts/run_authority_shape_preflight.py`
- `scripts/run_authority_leak_guard.py`
- `docs/governance/authority_shape_preflight.md`
- `docs/hop/preflight.md`
- `contracts/governance/authority_shape_vocabulary.json`
- `docs/architecture/system_registry.md`
