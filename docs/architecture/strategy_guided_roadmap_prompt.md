# Strategy-Guided Roadmap Prompt (Governed)

Use this prompt only for roadmap generation inside governed workflow seams.

## Operating Order (Strict)
1. `docs/architecture/strategy-control.md`
2. `docs/architecture/foundation_pqx_eval_control.md`
3. `docs/architecture/ai_operating_substrate_and_artifact_intelligence.md`
4. current repository state
5. current roadmap (`docs/roadmaps/system_roadmap.md` with required `docs/roadmap/system_roadmap.md` compatibility mirror)
6. source design documents / architecture artifacts (PDFs/data lake artifacts and governed source extracts)

## Mandatory Foundation + Substrate Pre-Check (Run Before Proposing Steps)
Compare repository state against all three authority documents and report:
- `docs/architecture/strategy-control.md`
- `docs/architecture/foundation_pqx_eval_control.md`
- `docs/architecture/ai_operating_substrate_and_artifact_intelligence.md`

Required findings before step proposal:
- must-add substrate components already present and governed
- components present but partial
- components present but bypassable/weak
- components missing
- artifact families already real vs only designed
- whether the minimum viable artifact-intelligence slice is buildable now
- whether the golden path is buildable

Apply mandatory status classes to each layer/component:
- `present_and_governed`
- `present_but_partial`
- `present_but_bypassable`
- `missing`
- `ambiguous`

Required coverage domains:
- schemas
- prompt/task lifecycle governance
- model adapter boundary compliance
- routing decision artifacts
- context admission artifacts
- PQX execution
- eval registry/slice coverage
- control logic
- enforcement
- replay
- tracing
- judgment reuse
- derived artifact intelligence jobs
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
- missing foundation/substrate pre-check classification
- proposes expansion while foundation or must-add substrate has `present_but_partial`, `present_but_bypassable`, `missing`, or `ambiguous` status in required layers/components

- Strategy Control Document is highest authority.
- Foundation document is mandatory architecture authority for roadmap generation.
- AI operating substrate document is mandatory substrate/intelligence authority for roadmap generation.
- Every roadmap step must explicitly align to strategy invariants from `docs/architecture/strategy-control.md`.
- Source docs are mandatory bounded grounding inputs.
- Foundation-before-expansion and substrate-before-expansion are required.
- Output must be structured and provenance-bearing.
- Detect and report drift before proposing expansion.
- If authorities and roadmap disagree, record mismatch as a hardening gap and prioritize closure; do not rewrite architecture.

## Sequencing Rules (Hard Gate)
- Missing or weak foundation/must-add substrate components must be prioritized before expansion.
- If must-add substrate gaps remain, roadmap steps must prioritize substrate build/hardening before broader workflow expansion, more agentic behavior, model breadth expansion, artifact-family breadth expansion, or autonomy expansion.
- Reject roadmap steps that expand agent behavior, workflows, model/provider breadth, or artifact breadth while foundation/substrate is incomplete.
- No broader capability advancement is compliant until foundation chain and must-add substrate chain are non-bypassable and governed.

## Required Output Structure

### Current Strategy Risks
- Enumerate current violations or pressure points against strategy invariants.

### Foundation and Substrate Gap Classification
- Classify each required foundation layer and must-add substrate component (`present_and_governed`, `present_but_partial`, `present_but_bypassable`, `missing`, `ambiguous`).
- Explicitly state whether the golden path and minimum viable artifact-intelligence slice are buildable.

### Current Source Misalignment Risks
- Enumerate gaps between implemented seams and source-authorized architecture grounding.

### Roadmap Table
| ID | Prompt | Status | What It Does | Why It Matters | Strategy Alignment | Source Grounding | Dependency Class | Primary Trust Gain |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Each roadmap step MUST declare one `Dependency Class` value:
- `foundation hardening`
- `substrate build`
- `substrate hardening`
- `artifact intelligence build`
- `depends on missing substrate`
- `blocked until hard gate passes`

### Example Row (Anchor Pattern)
| ID | Prompt | Status | What It Does | Why It Matters | Strategy Alignment | Source Grounding | Dependency Class | Primary Trust Gain |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EX-01 | Add eval gating | Not Run | Adds eval enforcement | Prevents unverified outputs | Strengthens Eval Invariants 6–9; Control Rule fail-closed | Foundation chain eval→control seam | foundation hardening | eval coverage |

### Recommended Next Hard Gate
- Single gate recommendation with rationale tied to trust-before-speed and foundation/substrate-first sequencing.

## Provenance Block (Mandatory)
Every roadmap output must include:
- `strategy_ref` (path + version/date)
- `strategy_version` (`strategy-control.md::<hash_or_version>`)
- `foundation_ref` (`docs/architecture/foundation_pqx_eval_control.md` + version/date)
- `substrate_ref` (`docs/architecture/ai_operating_substrate_and_artifact_intelligence.md` + version/date)
- `source_refs[]` (source id + path + enforcement purpose)
- `invariant_checks_applied[]`
- `foundation_checks_applied[]`
- `substrate_checks_applied[]`
- `foundation_gap_summary[]`
- `substrate_gap_summary[]`
- `drift_detected[]`
- `allowed_now_rationale` (why step is allowed now instead of later)

## Fail-Closed Conditions
Reject roadmap output when any of the following is true:
- strategy reference missing
- strategy_version lock missing
- foundation reference missing
- substrate reference missing
- source grounding list missing or empty
- invariant checks missing
- foundation checks missing
- substrate checks missing
- any roadmap step missing explicit strategy-invariant alignment
- any roadmap step missing dependency class
- any roadmap step missing primary trust gain
- roadmap includes agent-first or prompt-first step framing
- roadmap proposes capability without governance control integration
- roadmap proposes expansion while foundation/substrate is incomplete
- drift detected but not stabilized
- roadmap step justification lacks trust rationale
