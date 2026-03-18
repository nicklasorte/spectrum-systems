# AGENTS.md — modules/slide_intelligence

## Ownership
Slide Intelligence module — treats slides as first-class governed technical artifacts.
Implementation source of truth: `spectrum_systems/modules/slide_intelligence.py`

## Local purpose
Extract structured signals from slide decks: technical claims, assumptions, entities, gaps, and alignment with transcripts and working papers.
All outputs must conform to the `slide_intelligence_packet` contract (`contracts/schemas/slide_intelligence_packet.schema.json`).

## Constraints
- Do not add LLM calls or embedding dependencies directly in this module. Route through the canonical prompt interface.
- Gap detection logic lives in `spectrum_systems/modules/gap_detection.py`. Do not duplicate it here.
- All public functions must be deterministic given the same inputs.
- New extraction functions (A–K naming convention) must be added in sequence and documented in the module docstring.

## Required validation surface
Before any `BUILD` or `WIRE` prompt is marked complete:
1. Run `pytest tests/test_gap_detection.py` — gap detection must pass.
2. Verify the `slide_intelligence_packet` contract is satisfied by at least one golden-path fixture in `contracts/examples/`.
3. Run `.codex/skills/golden-path-check/run.sh slide_intelligence_packet`.

## Files that must not be changed casually
| File | Reason |
| --- | --- |
| `contracts/schemas/slide_intelligence_packet.schema.json` | Contract-first rule — changes require a PLAN prompt and version bump |
| `contracts/schemas/slide_deck.schema.json` | Upstream contract — changing it breaks all slide consumers |
| `spectrum_systems/modules/gap_detection.py` | Shared gap detection — changes affect slide and transcript modules |
| `contracts/standards-manifest.json` | Version registry — update only after a contract version bump |

## Nearby files (read before editing)
- `spectrum_systems/modules/slide_intelligence.py` — current implementation
- `spectrum_systems/modules/gap_detection.py` — gap detection dependency
- `contracts/schemas/slide_intelligence_packet.schema.json` — output contract
- `tests/test_gap_detection.py` — primary test surface
