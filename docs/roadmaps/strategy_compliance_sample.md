# Strategy Compliance Sample Roadmap

## Current Strategy Risks
- Invariant 6 (eval-mandatory) is under-enforced in progression gates.
- Invariant 15 (replayable) lacks complete trace linkage for behavior-changing policy actions.

## Current Source Misalignment Risks
- Runtime promotion checks do not consistently cite replay artifacts in control decisions.

## Roadmap Table
| ID | Prompt | Status | What It Does | Why It Matters | Strategy Alignment | Primary Trust Gain |
| --- | --- | --- | --- | --- | --- | --- |
| EX-01 | Add eval gating | Not Run | Adds fail-closed eval enforcement at promotion boundary and records trace IDs for each block/allow decision. | Prevents unverified outputs from advancing while preserving deterministic replay for audits. | Strengthens Eval Invariants 6–9; Control Rule fail-closed; replayable invariant with trace-complete decision logs. | eval coverage |
| EX-02 | Bind policy to replay pack | Not Run | Requires policy actions that change system behavior to emit replay bundle pointers and trace implications in enforcement records. | Makes behavior changes reconstructable and auditable across Observe→Enforce loop stages. | Control authority externalized + replayable invariants; O/I/D/E control-loop linkage with required trace implications. | replay determinism |

## Recommended Next Hard Gate
- Enforce a promotion gate requiring eval pass evidence plus replay/trace-complete enforcement records.

## Provenance Block
- `strategy_ref`: `docs/architecture/strategy-control.md` (2026-03-31)
- `strategy_version`: `strategy-control.md::sample-v1`
- `source_refs[]`:
  - `runtime_promotion_policy` (`docs/roadmaps/system_roadmap.md`) for gate sequencing controls
  - `strategy_control_invariants` (`docs/architecture/strategy-control.md`) for invariant mapping
- `invariant_checks_applied[]`:
  - eval-mandatory
  - control authority externalized
  - replayable
  - fail-closed
- `drift_detected[]`:
  - partial replay pointer coverage in current behavior-changing policy actions
- `allowed_now_rationale`:
  - this work hardens trust-before-speed by requiring invariant and trust-gain evidence before promotion.
