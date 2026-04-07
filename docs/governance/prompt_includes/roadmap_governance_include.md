# Roadmap Governance Include (Reusable)

> Mandatory include for roadmap-generation prompts touching sequencing, expansion, or execution policy.

## Required authority load order
1. `docs/governance/strategy_control_doc.md`
2. `docs/architecture/foundation_pqx_eval_control.md`
3. repository state evidence
4. active roadmap authority
5. supporting source/design material

Do not reorder this stack.

## Hard sequencing rules
- **Strategy-first ordering:** derive roadmap decisions from strategy invariants before proposing any step.
- **Foundation before autonomy:** close foundation/control-loop gaps before autonomy or throughput expansion.
- **Hardening before expansion:** if a seam is partial, bypassable, ambiguous, or missing, prioritize hardening slices first.
- **Incomplete earlier slices block later expansion:** unresolved earlier foundational slices must be listed and scheduled before any later capability expansion.

## Anti-pattern rejection (must reject)
- Capability expansion without explicit trust gain.
- New orchestration complexity that bypasses eval, policy, trace, or certification.
- Roadmap rows that omit failure-binding or control-loop path.
- Deferring recurrence prevention while scaling execution breadth.

## Drift handling rules
- Classify drift as `warning`, `freeze_candidate`, or `blocking`.
- For each detected drift signal, emit a corrective step in the roadmap output.
- If any blocking drift exists, expansion rows must be excluded until closure rows are first.

## Required output fields for every roadmap step
Each step must include:
- `step_id`
- `title`
- `depends_on`
- `target_layer` (`stable` or `replaceable`)
- `trust_gain`
- `risk_if_skipped`
- `invariant_guarded`
- `control_loop_stage`
- `proof_artifacts`
- `exit_criteria`
- `drift_signals_monitored`

## Required pre-expansion check
Before adding any expansion step, explicitly report:
1. unresolved earlier foundation slices,
2. why expansion is blocked or allowed,
3. the exact hardening step(s) that clear the block.
