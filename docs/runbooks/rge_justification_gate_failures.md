# Runbook: RGE Phase Justification Gate Failures

**System:** RGE
**Gate:** phase_justification_gate (Principle 1 - Kill Complexity Early)
**Failure artifact type:** phase_justification_record (decision=block)

---

## WHAT

The RGE Phase Justification Gate blocks any proposed roadmap phase that cannot
prove it prevents a specific failure, improves a measurable signal, and
strengthens a canonical loop leg.

Every proposal emits a `phase_justification_record`. A record with
`decision == "block"` halts the roadmap generator for that phase.

## WHY

Phases that cannot justify themselves accrete as dead weight. Principle 1 keeps
the roadmap expensive to add to and cheap to delete from. If the gate blocks,
the phase is not yet ready - not that the gate is wrong.

## SYMPTOMS

```
FAILURE: RGE/phase_justification_gate
decision: block
errors:
  - failure_prevented: missing - ...
  - signal_improved: not measurable ('makes things better')
  - loop_leg: 'FOO' is not a canonical loop leg - ...
```

## DIAGNOSIS STEPS

1. Read the `errors` list on the `phase_justification_record`. Each entry
   names a specific field and a specific defect.
2. Classify: missing field, too short, vague language, non-measurable signal,
   or non-canonical loop leg.
3. Confirm the proposer is emitting the expected field set:
   `failure_prevented`, `signal_improved`, `loop_leg`.

## FIX

- `failure_prevented`: name the specific failure mode (>=15 chars, no vague
  terms). Example: "Phases ship without eval coverage - eval_coverage_rate
  drops below 80%".
- `signal_improved`: include a number, a rate, or a threshold. Example:
  "eval_coverage_rate rises from 62% to 90%".
- `loop_leg`: use one of `AEX, PQX, EVL, TPA, CDE, SEL, REP, LIN, OBS, SLO`.

Re-submit the phase through the filter.

## PREVENTION

- Generators should template these fields at construction time.
- Code review for phase proposals should verify non-vague language.
- Add unit tests that exercise the generator with representative inputs.
