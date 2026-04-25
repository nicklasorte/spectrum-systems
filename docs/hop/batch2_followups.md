# HOP-BATCH-2 Followups

Items intentionally deferred from BATCH-1, with rationale and acceptance
criteria for closure in BATCH-2.

## F-06 — Hard-bounded streaming for `show-frontier`

**Current behavior:** `hop_cli.cmd_show_frontier` streams the index but
loads every score artifact into a Python list before computing the
frontier. With ~10⁵ scores, the working set fits but is unbounded.

**BATCH-2 acceptance:**
- Frontier computation runs in two passes: first pass counts non-dominated
  candidates per chunk; second pass merges chunk frontiers using the
  monotone Pareto property.
- Memory budget per CLI invocation is bounded by `--max-frontier-window`.
- The default window keeps total resident memory under 50 MB for any
  single run.

## Autonomous proposer

Out of scope for BATCH-1 by design. BATCH-2 will introduce a `proposer/`
module that emits new harness candidates, but every emission still runs
through `hop.admission.admit_candidate` before reaching the evaluator.
The proposer is forbidden from modifying eval cases or store artifacts;
those rights remain with the evaluator and the store.

## Distributed / concurrent writes

`ExperienceStore` is a single-process append-only store. BATCH-2 will add
file-locking around the index and per-artifact write to support multi
process evaluators. BATCH-1's single-process invariant is captured by
`tests/hop/test_experience_store.py`.

## Calibrated trace_completeness

In BATCH-1, `trace_completeness = (count of complete traces) /
case_count`. A future BATCH-2 refinement scores a trace's *step coverage*
(how many of the required ops are present) so partial traces can still
contribute. Current BATCH-1 behavior is conservative — partial coverage
counts as zero.
