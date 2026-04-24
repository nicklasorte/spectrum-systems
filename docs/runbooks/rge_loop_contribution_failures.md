# Runbook: RGE Loop Contribution Check Failures

**System:** RGE
**Gate:** loop_contribution_checker (Principle 2 - Build Fewer, Stronger Loops)
**Failure artifact type:** loop_contribution_record (decision=block)

---

## WHAT

The Loop Contribution Checker blocks phases that:

1. Target a non-canonical loop leg.
2. Target a leg currently in active drift (resolve drift first).
3. Target a saturated leg (max 8 contributors; strengthen existing instead).

Emits `loop_contribution_record` on every decision.

## WHY

Fewer, stronger loops is a load-bearing invariant. Adding more contributors to
a drifting or saturated leg increases failure surface and obscures root cause.

## SYMPTOMS

```
FAILURE: RGE/loop_contribution_checker
decision: block
errors:
  - Loop leg 'EVL' is in active drift. Propose a STRENGTHEN-EVL phase first.
  - Loop leg 'TPA' is saturated (8/8 contributors).
```

## DIAGNOSIS STEPS

1. Check `active_drift_legs` on the record. Is the target leg listed?
2. Check `leg_saturation`. Is the count at or above 8?
3. Check `loop_leg`. Is it a canonical code?

## FIX

- **Drift:** Propose a `STRENGTHEN-<leg>` phase to resolve drift first.
  Deletion and strengthen phases bypass the drift block.
- **Saturation:** Strengthen an existing contributor, or propose a deletion
  that reduces count under 8 first.
- **Non-canonical leg:** Pick from
  `AEX, PQX, EVL, TPA, CDE, SEL, REP, LIN, OBS, SLO`.

## PREVENTION

- Refresh `roadmap_signal_bundle` before generation so drift legs are current.
- Keep a live `leg_saturation` map; audit quarterly.
- Reject "add" phases when a "strengthen" phase would achieve the same signal.
