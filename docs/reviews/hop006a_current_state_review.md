# HOP-006A — Current State Review

Date: 2026-04-28  
Prompt type: REVIEW  
Scope: design-only next-phase pass for HOP with AGS canonical-registry scope repair.

## 1) What HOP currently does

HOP currently operates as an advisory-only harness optimization substrate with a bounded execution loop over candidate harnesses.

- Stores governed optimization artifacts (`candidate`, `run`, `score`, `trace`, `frontier`, failure hypotheses) via the experience store and artifact helpers.
- Evaluates candidates against versioned eval sets through a sandboxed evaluator/validator path.
- Runs deterministic baseline + mutation-template proposer flow and records frontier movement.
- Produces readiness and rollback **signals** (not decisions), and emits control advisories for downstream canonical owners.
- Keeps the FAQ hard workflow (`transcript -> FAQ`) as canonical hard workflow #1, with explicit eval judges/failure modes documented.

Representative implementation/doc surfaces:

- `spectrum_systems/modules/hop/experience_store.py`
- `spectrum_systems/modules/hop/evaluator.py`
- `spectrum_systems/modules/hop/validator.py`
- `spectrum_systems/modules/hop/frontier.py`
- `spectrum_systems/modules/hop/proposer.py`
- `spectrum_systems/modules/hop/optimization_loop.py`
- `docs/hop/golden_workflow.md`
- `docs/hop/preflight.md`

## 2) What HOP currently does not do

HOP does **not** own release, rollback, promotion, certification, control, enforcement, approval, or judgment authority.

- It does not gate promotion/release outcomes; REL/GOV/CDE remain canonical owners.
- It does not perform enforcement actions; SEL/ENF remain canonical owners.
- It does not make final policy/judgment decisions; JDX/CDE/GOV remain canonical owners by cluster.
- It does not define a production extraction workflow for transcript -> issue/risk/action/open-question/assumption yet (HOP-006A is design-only).

Current boundaries are explicit in system registry language and HOP preflight guidance, including advisory-only vocabulary and guard scripts.

## 3) Remaining bottlenecks

1. **No implemented second hard workflow**: extraction workflow is specified at design level but not implemented (no runtime, schema, eval-set wiring yet).
2. **Eval hardness governance pending**: baseline-ceiling enforcement for extraction (`score < 0.85` search) is design-specified but not yet executable until HOP-006B lands.
3. **Cross-turn ambiguity handling gap**: current deterministic baseline patterns are intentionally limited and will underperform on attribution/conflict ambiguity classes.
4. **Design-to-build traceability risk**: if HOP-006B implementation drifts from the design fields and advisory-only semantics, regressions could re-open authority-shape leakage.

## 4) Stale docs or misleading language risks

Current documents are mostly aligned, but there are notable drift risks to monitor during HOP-006B:

- Any phrase that frames HOP as deciding/gating outcomes (even in explanatory prose) can trigger authority-shape confusion.
- Registry phrasing in non-owning sections must continue to use boundary clarification language (`external to`, `never decides`, `downstream canonical owners`) rather than ownership claims.
- Extraction workflow references must remain explicitly design-only until schemas/evals/runtime land in HOP-006B.

## 5) Authority-boundary risks (current)

Highest-risk regression vectors:

1. Reintroduction of authority-shaped identifiers in HOP docs/code (e.g., `promotion_decision`, `blocks_promotion`).
2. Non-owning registry section language drifting into ownership claims (e.g., “HOP decides promotion”).
3. Future extraction schema drift introducing authority-bearing field names (`severity`, `requires_*`, `blocks_*`).
4. Held-out eval leakage attacks if sandbox read-deny wiring is bypassed at call sites.

Current mitigations already in place:

- AGS authority-shape preflight + regression test coverage over HOP scope.
- System registry guard and authority leak guard execution paths.
- Advisory-only signal framing (`*_signal`, `*_input`, `*_observation`) as normalized terminology.

## 6) HOP-006A review conclusion

Current state is sufficient for a design-only phase advancement: HOP remains advisory-only, FAQ workflow remains stable, and preflight guardrails are active. The next-phase extraction workflow is appropriate to proceed to implementation planning **only** with strict preservation of advisory-only semantics and hardened eval/held-out constraints defined in HOP-006A design + red-team artifacts.
