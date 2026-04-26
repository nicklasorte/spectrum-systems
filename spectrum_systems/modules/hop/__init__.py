"""
Harness Optimization Pipeline (HOP).

Governed substrate that stores full harness experience (code, traces, scores),
evaluates harness candidates against a versioned eval set, exposes queryable
history, and prevents eval gaming.

BATCH-1 ships the foundation: store + admission + safety + evaluator +
frontier + baseline harness.

BATCH-2 adds *bounded* optimization:

- ``proposer`` — generates candidate code from deterministic mutation
  templates; never writes to the store; never calls the evaluator.
- ``mutation_policy`` — admits/rejects proposals via path scope + AST
  scan; emits ``hop_harness_failure_hypothesis`` on violations.
- ``trace_diff`` — structured comparison artifact between two candidates'
  scores + traces.
- ``failure_analysis`` — causal hypothesis builder; consumes a trace diff
  and emits a ``causal_analysis`` failure hypothesis.
- ``optimization_loop`` — sole orchestrator of proposer ->
  mutation_policy -> admission -> evaluator -> store -> trace_diff ->
  failure_analysis -> frontier.

Authority boundaries (unchanged):

- The proposer is advisory only. It never decides, persists, or
  advances candidates; those rights live with the optimization loop, the
  evaluator, and (above HOP) the CDE/REL/GOV release path.
- HOP never self-attests: a candidate's frontier membership is an
  advisory readiness_signal, not a release_signal. Release advancement
  remains with REL/GOV/CDE per the project CLAUDE.md.
"""

from spectrum_systems.modules.hop import (  # noqa: F401
    admission,
    artifacts,
    baseline_harness,
    bootstrap,
    evaluator,
    experience_store,
    failure_analysis,
    frontier,
    mutation_policy,
    optimization_loop,
    patterns,
    proposer,
    sandbox,
    safety_checks,
    schemas,
    trial_runner,
    trace_diff,
    validator,
)
