# TLS-GUARD-01 — DELIVERY REPORT

## Scope

Add a local preflight that runs the exact authority checks needed for TLS
dependency-priority and 3LS dashboard changes before CI. The wrapper is
fast-feedback only — the binding gate remains
`scripts/run_authority_leak_guard.py` in CI.

## Files Modified / Created

- Created: `scripts/preflight_tls_priority.sh`
- Created: `docs/operations/tls_priority_preflight.md`
- Created: `docs/reviews/TLS-GUARD-01-DELIVERY-REPORT.md`
- Modified: `scripts/build_tls_dependency_priority.py` — added an optional
  `--candidates` flag so the wrapper can scope the printed summary to the
  operator's focus set (`H01,RFX,HOP,MET,METS`). The governed priority
  artifact still ranks the full registry; the flag only filters the printed
  summary, so no ranking semantics change.

## Pipeline

`scripts/preflight_tls_priority.sh` runs, in order:

1. `python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS`
2. `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json`
3. `python scripts/run_authority_leak_guard.py --base-ref main --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json`
4. `python -m pytest tests/tls_dependency_graph`

Dashboard surface detection: when `git diff --name-only ${BASE_REF} ${HEAD_REF}`
shows changes under `apps/dashboard-3ls/`, `apps/dashboard/`,
`app/dashboard/`, `app/dashboard-3ls/`, `components/dashboard/`,
`src/dashboard/`, or `spectrum_systems/dashboard/`, the wrapper prints:

```
Run dashboard-3ls tests before pushing.
```

## Acceptance Mapping

| Acceptance criterion                                         | Where it is satisfied                                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| Script exits non-zero on authority-shape or authority-leak failures | `WORST_RC` propagation in `scripts/preflight_tls_priority.sh` (each step's rc is captured and the worst non-zero is the wrapper exit code). |
| Script is referenced in TLS delivery reports                 | This report (`docs/reviews/TLS-GUARD-01-DELIVERY-REPORT.md`) and `docs/operations/tls_priority_preflight.md`. |
| No guard is weakened                                         | The wrapper invokes each guard with the same flags CI uses. The shape preflight runs in `--suggest-only`, which is non-mutating but still fails closed on leaks. The authority-leak guard runs unmodified. The pytest suite runs unmodified. The `--candidates` flag added to `build_tls_dependency_priority.py` does not change ranking semantics or the governed artifact — it only scopes the printed summary. |

## Documentation

- `docs/operations/tls_priority_preflight.md` documents:
  - when to run it
  - what each guard protects
  - forbidden vocabulary examples (canonical authority terms)
  - safe observer vocabulary examples (`_signal`, `_observation`,
    `_input`, `_recommendation`, `_finding`, `_evidence`, `_advisory`,
    `_request`, `_summary`)
  - the boundary statement (this is a static, non-owning preflight; the
    binding gate is the CI authority-leak guard)

## References

- `scripts/preflight_tls_priority.sh`
- `docs/operations/tls_priority_preflight.md`
- `scripts/build_tls_dependency_priority.py`
- `scripts/run_authority_shape_preflight.py`
- `scripts/run_authority_leak_guard.py`
- `tests/tls_dependency_graph/`
- `docs/governance/authority_shape_preflight.md`
- `docs/hop/preflight.md`
