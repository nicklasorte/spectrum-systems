# Strategy-Guided Roadmap Prompt (Governed)

Use this prompt only for roadmap generation inside governed workflow seams.

## Operating Order (Strict)
1. `docs/architecture/strategy-control.md`
2. `docs/architecture/foundation_pqx_eval_control.md`
3. current repository state
4. current roadmap (`docs/roadmaps/system_roadmap.md` with required `docs/roadmap/system_roadmap.md` compatibility mirror)
5. source design documents / architecture artifacts (PDFs/data lake artifacts and governed source extracts)

## Mandatory Foundation Pre-Check (Run Before Proposing Steps)
Compare repository state against `docs/architecture/foundation_pqx_eval_control.md` and report:
- foundation layers present
- foundation layers present but partial
- foundation layers present but bypassable
- foundation layers missing
- foundation layers ambiguous
- whether golden path is buildable

Apply mandatory status classes to each layer:
- `present_and_governed`
- `present_but_partial`
- `present_but_bypassable`
- `missing`
- `ambiguous`

Required coverage domains:
- schemas
- PQX execution
- eval system
- control logic
- enforcement
- replay
- tracing
- golden path

Treat `present_but_bypassable`, `missing`, and `ambiguous` as hardening priorities.

## Enforcement Requirements

## NON-NEGOTIABLE (STRICT MODE)
- Every step MUST reference at least one strategy invariant.
- Every step MUST reference at least one trust gain category.
- Every step MUST state primary trust gain.
- Every step MUST include explicit eval reference linkage.
- Every step MUST include explicit control-loop stage integration (Observe/Interpret/Decide/Enforce).
- For any step affecting system behavior, the step MUST explicitly state replay or trace implications.
- Every step MUST include replay and trace considerations for auditability.
- Roadmap generation MUST bind to `strategy_version: "strategy-control.md::<hash_or_version>"`.
- Missing alignment is invalid output.
- Missing these fields = invalid output.

## INVALID OUTPUT CONDITIONS
- missing Strategy Alignment
- missing Primary Trust Gain
- agent-first or prompt-first steps
- capability without eval/control/replay
- capability without governance
- missing foundation pre-check classification
- proposes expansion while foundation has `present_but_partial`, `present_but_bypassable`, `missing`, or `ambiguous` status in required layers

- Strategy Control Document is highest authority.
- Foundation document is mandatory architecture authority for roadmap generation.
- Every roadmap step must explicitly align to strategy invariants from `docs/architecture/strategy-control.md`.
- Source docs are mandatory bounded grounding inputs.
- Foundation-before-expansion is required.
- Output must be structured and provenance-bearing.
- Detect and report drift before proposing expansion.
- If foundation and roadmap disagree, record mismatch as a foundation gap and prioritize hardening; do not rewrite architecture.

## Sequencing Rules (Hard Gate)
- Missing or weak foundation must be prioritized before expansion.
- Reject roadmap steps that expand agent behavior, workflows, or artifact breadth while foundation is incomplete.
- No broader capability advancement is compliant until foundation chain is non-bypassable and governed.

## Required Output Structure

### Current Strategy Risks
- Enumerate current violations or pressure points against strategy invariants.

### Foundation Gap Classification
- Classify each required foundation layer (`present_and_governed`, `present_but_partial`, `present_but_bypassable`, `missing`, `ambiguous`).
- Explicitly state whether the golden path is buildable.

### Current Source Misalignment Risks
- Enumerate gaps between implemented seams and source-authorized architecture grounding.

### Roadmap Table
| ID | Prompt | Status | What It Does | Why It Matters | Strategy Alignment | Source Grounding | Foundation Dependency Status | Primary Trust Gain |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Each roadmap step MUST declare one Foundation Dependency Status value:
- `builds_foundation`
- `hardens_foundation`
- `depends_on_foundation`
- `blocked_by_foundation`

### Example Row (Anchor Pattern)
| ID | Prompt | Status | What It Does | Why It Matters | Strategy Alignment | Source Grounding | Foundation Dependency Status | Primary Trust Gain |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EX-01 | Add eval gating | Not Run | Adds eval enforcement | Prevents unverified outputs | Strengthens Eval Invariants 6–9; Control Rule fail-closed | Foundation chain eval→control seam | hardens_foundation | eval coverage |

### Recommended Next Hard Gate
- Single gate recommendation with rationale tied to trust-before-speed and foundation-first sequencing.

## Provenance Block (Mandatory)
Every roadmap output must include:
- `strategy_ref` (path + version/date)
- `strategy_version` (`strategy-control.md::<hash_or_version>`)
- `foundation_ref` (`docs/architecture/foundation_pqx_eval_control.md` + version/date)
- `source_refs[]` (source id + path + enforcement purpose)
- `invariant_checks_applied[]`
- `foundation_checks_applied[]`
- `foundation_gap_summary[]`
- `drift_detected[]`
- `allowed_now_rationale` (why step is allowed now instead of later)

## Fail-Closed Conditions
Reject roadmap output when any of the following is true:
- strategy reference missing
- strategy_version lock missing
- foundation reference missing
- source grounding list missing or empty
- invariant checks missing
- foundation checks missing
- any roadmap step missing explicit strategy-invariant alignment
- any roadmap step missing foundation dependency status
- any roadmap step missing primary trust gain
- roadmap includes agent-first or prompt-first step framing
- roadmap proposes capability without governance control integration
- roadmap proposes expansion while foundation is incomplete
- drift detected but not stabilized
- roadmap step justification lacks trust rationale
