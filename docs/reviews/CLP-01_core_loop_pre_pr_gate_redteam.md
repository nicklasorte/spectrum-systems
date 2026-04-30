# CLP-01 Core Loop Pre-PR Gate Red-team

## must_fix
- Missing CLP evidence for repo-mutating work could be treated as pass; fixed by fail-closed BLOCK in `agent_core_loop_proof.py`.
- CLP artifact authority scope could drift; fixed by enforcing `observation_only` and BLOCK on mismatch.

## should_fix
- Expand selected test execution to canonical selector once repo canonical selector wiring for this gate is finalized.

## observation
- CLP bundles evidence only and does not replace CI.
