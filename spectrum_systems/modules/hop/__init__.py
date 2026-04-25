"""
Harness Optimization Pipeline (HOP).

Governed substrate that stores full harness experience (code, traces, scores),
evaluates harness candidates against a versioned eval set, exposes queryable
history, and prevents eval gaming. HOP-BATCH-1 is the foundation layer; no
autonomous optimization runs here.

Module ownership boundaries:
- experience_store: append-only artifact persistence and indexing.
- validator: pre-eval interface validation; rejects malformed candidates.
- safety_checks: leakage / tamper detection; rejects gaming candidates.
- evaluator: runs candidates against eval set; produces score + trace artifacts.
- baseline_harness: deterministic transcript -> FAQ baseline candidate.
- frontier: Pareto frontier across (score, cost, latency, trace_completeness, eval_coverage).

HOP does NOT:
- modify candidates (no proposer in BATCH-1).
- execute closure or promotion decisions; those authorities live elsewhere.
- emit free-form findings (every artifact is schema-bound).
- bypass eval / schema validation under any failure mode.
"""

from spectrum_systems.modules.hop import (  # noqa: F401
    admission,
    artifacts,
    baseline_harness,
    evaluator,
    experience_store,
    frontier,
    safety_checks,
    schemas,
    validator,
)
