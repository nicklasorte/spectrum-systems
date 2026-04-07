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
