# Strategy-Guided Roadmap Prompt (Governed)

Use this prompt only for roadmap generation inside governed workflow seams.

## Operating Order (Strict)
1. `docs/architecture/system_strategy.md`
2. `docs/architecture/system_source_index.md`
3. current repository state
4. referenced source architecture docs

## Enforcement Requirements
- Strategy is highest authority.
- Source docs are mandatory bounded grounding inputs.
- Foundation-before-expansion is required.
- Output must be structured and provenance-bearing.
- Detect and report drift before proposing expansion.

## Required Output Structure

### Current Strategy Risks
- Enumerate current violations or pressure points against strategy invariants.

### Current Source Misalignment Risks
- Enumerate gaps between implemented seams and source-authorized architecture grounding.

### Roadmap Table
| ID | Prompt | Status | What It Does | Why It Matters | Strategy Alignment | Source Grounding | Primary Trust Gain |
| --- | --- | --- | --- | --- | --- | --- | --- |

### Recommended Next Hard Gate
- Single gate recommendation with rationale tied to trust-before-speed.

## Provenance Block (Mandatory)
Every roadmap output must include:
- `strategy_ref` (path + version/date)
- `source_refs[]` (source id + path + enforcement purpose)
- `invariant_checks_applied[]`
- `drift_detected[]`
- `allowed_now_rationale` (why step is allowed now instead of later)

## Fail-Closed Conditions
Reject roadmap output when any of the following is true:
- strategy reference missing
- source grounding list missing or empty
- invariant checks missing
- drift detected but not stabilized
- roadmap step justification lacks trust rationale
