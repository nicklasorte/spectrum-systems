# DESIGN NOTE — RAX-EVAL-01

RAX had become too test-authoritative: passing tests could still allow semantically weak or governance-incomplete outputs to appear advancement-ready.

RAX-EVAL-01 introduces a governed eval surface with explicit required eval definitions, deterministic case execution, structured eval artifacts, fail-closed missing-eval handling, and a bounded control-readiness artifact.

Reference architecture: `docs/architecture/rax_eval_surface.md`.
