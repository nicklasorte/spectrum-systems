# March 31, 2026 Roadmap Transition Note

## What changed
- The March 31 roadmap update is now integrated into governed authority in `docs/roadmaps/system_roadmap.md`.
- Compatibility mirror behavior remains active in `docs/roadmap/system_roadmap.md` for legacy PQX consumers.
- A mandatory **Control Loop Closure Gate** (CL-01..CL-05) is now explicitly inserted before broader expansion tracks.
- RE-05 reconciliation tightens sequencing to one dominant trust spine after CL closure: `NX-01..NX-03` only, then a mandatory Control Loop Closure Certification Gate proof review before any `NX-04+`.

## Why the prior roadmap alone was not enough
The prior roadmap established strong governance and execution foundations, but did not yet bind failure learning tightly enough to future policy and progression decisions to qualify as a true MVP closed-loop control system.

## Transition rule
Broader grouped expansion and later AI execution expansion remain subordinate to Control Loop Closure Gate completion. Until that gate is passed with artifact evidence, roadmap progression should prioritize convergence and learning-loop hardening over breadth.
Transition policy now treats proof-before-scale as a hard blocker: no grouped execution expansion, no certification/promotion expansion, and no AI execution expansion before trust-spine closure evidence is certified.
AI expansion (`NX-22..NX-24`) remains explicitly last and requires bounded-window longitudinal calibration + recurrence-prevention efficacy evidence.
