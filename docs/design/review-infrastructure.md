# Review Infrastructure

## Why Scoped, Infrastructure-Aware Reviews Are Required

Claude reviews of complex multi-file systems fail in predictable ways when the
reviewer must infer system intent from raw repository state. Without explicit
scope boundaries, reviews:

- Raise findings about unrelated subsystems that are out of scope for the
  current roadmap slice.
- Omit findings about the most critical paths because the reviewer does not
  know which files are on the golden path.
- Fail to anchor findings to specific contracts, tests, or design documents
  because the reviewer does not know which artifacts are authoritative for the
  subsystem.
- Produce generic recommendations that could apply to any codebase rather than
  spectrum-specific, contract-grounded fixes.

The review infrastructure in this repository solves this by assembling a
**review pack** before every review — a structured bundle of scope context,
contract references, test references, design doc references, and known failure
modes that Claude receives as explicit input.

---

## How Review Packs Work

### 1. Review Manifests

Each reviewable subsystem has a **review manifest** stored in
`reviews/manifests/<scope_id>.review.json`. A manifest specifies:

| Field | Purpose |
|---|---|
| `scope_id` | Unique identifier for the subsystem (e.g. `p_gap_detection`) |
| `title` | Human-readable subsystem name |
| `purpose` | What the subsystem does |
| `golden_path_role` | How this subsystem contributes to the end-to-end golden path |
| `in_scope_files` | Exact file paths that are in scope for this review |
| `related_contracts` | Contract schemas that govern inputs/outputs |
| `related_tests` | Test files that exercise this subsystem |
| `related_design_docs` | Design documents describing intended behaviour |
| `upstream_dependencies` | Systems that feed this subsystem |
| `downstream_consumers` | Systems that consume this subsystem's outputs |
| `invariants` | Conditions that must hold for the subsystem to be correct |
| `known_edge_cases` | Edge cases that must be handled |
| `known_failure_modes` | IDs from the failure mode registry |

### 2. Failure Mode Registry

`reviews/failure_modes/failure_mode_registry.json` is a shared registry of
known failure modes across transcript/slide/gap/working-paper systems. Each
entry includes:

- `id` — stable identifier referenced by manifests
- `title` — short human-readable name
- `description` — what goes wrong and why
- `affected_layers` — which subsystems are at risk
- `detection_signals` — observable indicators that this failure has occurred
- `likely_downstream_impact` — what breaks downstream if this failure is undetected

### 3. Review Pack Assembly

The `review_orchestrator` module assembles a review pack by:

1. Loading the manifest for the requested `scope_id`.
2. Resolving all failure mode IDs in `known_failure_modes` against the registry.
3. Returning a structured dict with `file_list`, `contract_list`, `test_list`,
   `design_docs_list`, and `failure_modes_list`.

```python
from spectrum_systems.modules.review_orchestrator import build_review_pack

pack = build_review_pack("p_gap_detection")
```

### 4. Prompt Rendering

The orchestrator renders a populated Claude review prompt by substituting
manifest data into `templates/review/claude_review_prompt_template.md`.

```python
from spectrum_systems.modules.review_orchestrator import render_claude_review_prompt

prompt = render_claude_review_prompt("p_gap_detection")
```

The rendered prompt instructs Claude to:
- Review only the scoped subsystem.
- Anchor every finding to a file, contract, test, or design doc.
- Classify findings by severity and category.
- Emit output matching the review contract schema.
- Include failure scenarios for each known failure mode.
- End with a `GO`, `GO_WITH_FIXES`, or `NO_GO` verdict.

### 5. CLI Usage

```bash
# Build and display a review pack summary
python scripts/build_review_pack.py --scope-id p_gap_detection

# Render a Claude prompt and write it to a file
python scripts/render_claude_review_prompt.py --scope-id p_gap_detection --output /tmp/prompt.md

# Validate a Claude review output JSON file
python scripts/validate_review_output.py --input reviews/output/sample.json
```

---

## How Claude Outputs Are Validated

Claude review outputs must conform to `standards/review-contract.schema.json`.
The schema enforces:

- Required fields: `review_id`, `scope_id`, `review_type`, `reviewed_at`,
  `verdict`, `findings`.
- Verdict restricted to `GO | GO_WITH_FIXES | NO_GO`.
- Every finding must include `finding_id`, `severity`, `category`, `title`,
  `why_it_matters`, `recommended_fix`, `fix_type`, `downstream_risk`, and
  `priority_rank`.
- Finding `severity` restricted to `critical | high | medium | low`.
- Finding `category` restricted to the canonical set: `architecture`, `contract`,
  `validation`, `alignment`, `extraction-quality`, `silent-failure`,
  `golden-path`, `traceability`, `test`.
- Finding `fix_type` restricted to `patch | refactor | redesign`.
- `additionalProperties: false` at the top level prevents schema drift.

Validation is performed by the `validate_review_output` function in the
orchestrator module:

```python
from spectrum_systems.modules.review_orchestrator import validate_review_output

result = validate_review_output("reviews/output/sample.json")
if result["passed"]:
    print(f"Review passed: verdict = {result['verdict']}")
else:
    for error in result["errors"]:
        print(f"  ERROR: {error}")
```

---

## How This Supports Roadmap Checkpoints and Governance

### Roadmap Slice Reviews

Each roadmap slice (P, P+1, Q, …) maps to a review manifest. Before a slice
can be promoted to the next stage:

1. A review pack is built for the slice's scope ID.
2. The rendered prompt is passed to Claude.
3. Claude's output is validated against the review contract schema.
4. The verdict determines whether the slice proceeds:
   - `GO` — proceed to next slice.
   - `GO_WITH_FIXES` — address priority fix stack, then proceed.
   - `NO_GO` — halt; critical findings must be resolved.

### Governance Integration

- Review outputs stored in `reviews/output/` are versioned artifacts that
  support audit trails for regulatory submissions.
- The `priority_fix_stack` and `minimum_bar_to_proceed` fields create an
  explicit, machine-readable gate that CI workflows can enforce.
- The `failure_scenarios` field pre-populates risk registers for downstream
  governance review cycles.
- Review manifests are the authoritative record of which files, contracts,
  tests, and design docs are in scope for each subsystem — preventing scope
  creep in review discussions.

### Reusability

New roadmap slices require only:
1. A new manifest in `reviews/manifests/<scope_id>.review.json`.
2. Any new failure modes added to `reviews/failure_modes/failure_mode_registry.json`.

No changes to the orchestrator, scripts, or schemas are needed.

---

## File Index

| Path | Purpose |
|---|---|
| `standards/review-contract.schema.json` | Canonical JSON Schema for review contract outputs |
| `reviews/manifests/` | Per-scope review manifest files |
| `reviews/failure_modes/failure_mode_registry.json` | Shared failure mode registry |
| `reviews/review-packs/` | Generated review pack outputs (gitignored by default) |
| `reviews/scorecards/` | Review scorecard outputs |
| `reviews/output/` | Claude review output JSON files for validation |
| `templates/review/claude_review_prompt_template.md` | Prompt template for Claude reviews |
| `templates/review/review_output_template.json` | Output template scaffolding |
| `spectrum_systems/modules/review_orchestrator.py` | Core orchestrator module |
| `scripts/build_review_pack.py` | CLI: build and display a review pack |
| `scripts/render_claude_review_prompt.py` | CLI: render a Claude prompt |
| `scripts/validate_review_output.py` | CLI: validate a review output |
| `tests/test_review_orchestrator.py` | Tests for the orchestrator module |
| `tests/test_review_contract_schema.py` | Tests for the review contract schema |
