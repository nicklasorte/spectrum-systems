# Governance Layer README

## Purpose
The governance layer makes strategy and control obligations explicit, reusable, and testable across planning, roadmap generation, architecture review, and implementation execution.

It exists to prevent drift from trust-critical invariants and to ensure Spectrum Systems expands only when foundation controls are demonstrably closed.

## Authoritative document
**Primary authority for governance decisions in this layer:**
- `docs/governance/strategy_control_doc.md`

All governance artifacts in `docs/governance/` must be interpreted as implementation guidance and enforcement wiring derived from that document. If guidance conflicts, `strategy_control_doc.md` wins.

## Document classes

### Governance documents (this directory)
Use these for policy authority, enforcement expectations, prompt loading rules, drift signals, and workflow-level control obligations.

### Architecture documents (`docs/architecture/`)
Use these for system design, decomposition, and mechanism-level structure. Architecture describes how systems are built; governance decides when and under what controls those systems may progress.

### Raw/reference documents (`docs/source_structured/`, historical reviews, notes)
Use these as inputs or evidence. They are not automatic policy authority unless explicitly promoted through governance controls.

## Workflow usage model

### Roadmap generation
Roadmap prompts must load:
1. `docs/governance/strategy_control_doc.md`
2. `docs/governance/prompt_includes/roadmap_governance_include.md`

Roadmap outputs must prioritize foundation hardening and incomplete earlier slices before later expansion.

### Architecture review
Architecture reviews must load:
1. `docs/governance/strategy_control_doc.md`
2. `docs/governance/architecture_review_checklist.md`
3. `docs/governance/drift_signals.md`

Reviews must identify invariant risk and block expansion when bypasses or replayability regressions are present.

### Implementation prompts
Codex implementation prompts touching control/reliability/governance surfaces must load:
1. `docs/governance/strategy_control_doc.md`
2. `docs/governance/prompt_includes/implementation_governance_include.md`
3. `docs/governance/prompt_contract.md`

## Supersession and ADR requirements
The following change classes require explicit supersession note or ADR treatment before merge:
- Any change that modifies or reinterprets strategy invariants.
- Any change that alters authoritative input order for roadmap generation.
- Any change that weakens fail-closed behavior, certification gates, eval discipline, trace/replay obligations, or control-loop closure gates.
- Any introduction of alternate governance authority paths that could create ambiguity.

Recommended path:
1. Propose change with explicit rationale and affected invariant(s).
2. Record supersession/ADR artifact under `docs/adr/` or `docs/review-actions/`.
3. Update `docs/governance/governance_manifest.json` and dependent prompt includes in the same change set.

## Fail-Closed Prompt Enforcement Model

Prompt governance is now enforced through preflight validation instead of advisory-only guidance.

### Enforcement mechanics
- Enforced preamble: `docs/governance/prompt_includes/ENFORCED_PREAMBLE.md`
- Source-loading include: `docs/governance/prompt_includes/source_input_loading_include.md`
- Prompt checker: `scripts/check_governance_compliance.py`
- Prompt wrapper: `scripts/run_prompt_with_governance.py`
- Execution rules: `docs/governance/prompt_execution_rules.md`
- Governed prompt surface registry: `docs/governance/governed_prompt_surfaces.json`
- Governed prompt registry guide: `docs/governance/governed_prompt_surfaces.md`
- CI enforcement mapping: `docs/governance/ci_enforcement.md`

### What fail-closed means
If a prompt omits any required governance reference, the checker returns failure (non-zero exit), and wrapper execution is blocked.
No silent bypass is allowed.

### Prompt template usage
Use repository-native templates in `docs/governance/prompt_templates/`:
- `roadmap_prompt_template.md`
- `implementation_prompt_template.md`
- `architecture_review_prompt_template.md`

Each template already wires:
- enforced preamble include,
- source-input loading include,
- relevant governance include,
- explicit sections for inputs, constraints, task, and output requirements.

### Running governance preflight
- Validate file:
  - `python scripts/check_governance_compliance.py --file <prompt_file>`
- Validate text:
  - `python scripts/check_governance_compliance.py --text "<prompt_text>"`
- Wrapper flow:
  - `python scripts/run_prompt_with_governance.py <prompt_file>`
- Drift sync test:
  - `pytest tests/test_governed_prompt_surface_sync.py`

A missing governance reference is a blocking defect and must be remediated before prompt execution.
