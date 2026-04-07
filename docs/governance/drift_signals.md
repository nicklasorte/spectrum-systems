# Drift Signals Operating Note

Operational severity model derived from `docs/governance/strategy_control_doc.md`.

## Warning signals
Use when integrity is at risk but not yet bypassing hard controls.
- Partial evidence linkage between failure, eval, and policy artifacts.
- Incomplete observability for changed trust-critical seams.
- Replaceable-layer expansion with weak stable-layer reinforcement.
- Missing explicit trust gain field in roadmap or implementation reports.

## Freeze-candidate signals
Use when progression should pause pending hardening confirmation.
- Foundation layer is present but bypassable or ambiguous.
- Recurrence prevention assets are missing for known critical failure classes.
- Control decisions exist but enforcement outcome linkage is weak/incomplete.
- Replay artifacts are present but non-deterministic or incomplete for changed scope.

## Blocking signals
Use when expansion must stop immediately.
- Missing/omitted strategy authority in governance-critical prompts.
- Direct bypass around eval, trace, policy, certification, or enforcement.
- Contradictory authority paths with no explicit supersession/ADR.
- Roadmap expansion proposed while unresolved foundational blocking gaps remain.

## Required responses by severity
- **warning:** create corrective backlog item with owner, due slice, and verification evidence.
- **freeze_candidate:** block expansion rows; schedule hardening slice first; require review sign-off.
- **blocking:** fail closed; halt progression; emit remediation artifact and re-run governance checks before continuation.

## Required appearance in operating artifacts
Drift signals must be explicitly reported in:
- roadmap generation outputs (drift classification + corrective slices),
- architecture reviews (severity + gate decision),
- implementation delivery reports (detected/mitigated/newly introduced signals).

Minimum reporting fields:
- `signal_id`
- `severity`
- `trigger_condition`
- `affected_invariant`
- `required_response`
- `closure_evidence`
