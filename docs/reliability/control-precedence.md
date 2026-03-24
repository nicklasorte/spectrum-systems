# Control / Release Decision Precedence

Canonical precedence for governed trust decisions is:

`rollback > block/freeze > hold > warn > promote`

## Term mapping

- `rollback` — release rollback action (SF-14 release/canary)
- `block` / `freeze` — blocking control responses (SF-05/SF-11 control-loop dialect)
- `hold` — do not promote; wait for remediation (release comparison threshold failure)
- `warn` — non-blocking caution requiring follow-up
- `promote` — allow release progression

`block` and `freeze` are both treated as blocking outcomes in the same precedence tier.

## Enforcement

- Runtime helper: `spectrum_systems/modules/runtime/decision_precedence.py`
- Release/canary decision selection uses this precedence helper to avoid implicit ordering drift.
- CI/control paths reuse the same blocking tier semantics (`freeze|block`) when policy says responses are blocking.
