# Roadmap Generator Authority Note

## Mandatory Authority Inputs
Roadmap generator execution must use both:
1. `docs/architecture/strategy-control.md`
2. `docs/architecture/foundation_pqx_eval_control.md`

The foundation document is the canonical system architecture spec for the PQX → eval → control → enforcement chain and replay/trace closure.

## Canonical Input Order (Required)
1. `docs/architecture/strategy-control.md`
2. `docs/architecture/foundation_pqx_eval_control.md`
3. current repository state
4. `docs/roadmaps/system_roadmap.md`
5. source design documents / architecture artifacts

## Mandatory Foundation Comparison Before Planning
Before proposing roadmap steps, the generator must compare repository state against `docs/architecture/foundation_pqx_eval_control.md` and classify:
- present_and_governed
- present_but_partial
- present_but_bypassable
- missing
- ambiguous

Required domains:
- schemas
- PQX execution
- eval system
- control logic
- enforcement
- replay
- tracing
- golden path

## Expansion Block Rule
Expansion is blocked when foundation is incomplete.

Foundation incomplete includes any required domain classified as:
- present_but_partial
- present_but_bypassable
- missing
- ambiguous

When incomplete, roadmap steps must prioritize foundation build/hardening and must not expand agent behavior, workflows, or artifact breadth.

## Conflict Handling Rule
If roadmap and foundation disagree:
- record mismatch as a foundation gap,
- prioritize closure in roadmap sequencing,
- do not rewrite foundation architecture inside roadmap generation.

## Prompt Surface Normalization
- Canonical reusable generator prompt: `docs/architecture/strategy_guided_roadmap_prompt.md`
- This note is the canonical authority companion for generator behavior.
- No competing roadmap generator prompt variants may be used without explicit deprecation/normalization.
