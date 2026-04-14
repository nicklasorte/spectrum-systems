# AGENTS.md

## Purpose
Durable operating instructions for agents working in `spectrum-systems`.

This repository is the governance and control-plane surface for a governed runtime.

## Canonical sources
All high-impact decisions must align to:
1. `README.md` (system identity and operating model)
2. `docs/architecture/system_registry.md` (canonical system roles and ownership)

If any instruction conflicts with these sources, treat it as a defect and correct the conflicting surface.

## Agent roles
- **Claude**: architecture reasoning, risk assessment, and review findings.
- **Codex**: repository execution and deterministic multi-file updates.
- **Copilot**: downstream implementation repository coding.

## Canonical runtime rules
1. **Artifact-first execution**
2. **Fail-closed behavior**
3. **Promotion requires certification**

These rules are non-negotiable across prompts, plans, and governance docs.

## Canonical system roles
Use role ownership exactly as defined in `docs/architecture/system_registry.md`.

Do not duplicate, subset, or redefine ownership sets in other governance documents.

## Prompt type system
Each prompt must declare exactly one primary type:
- `PLAN`
- `BUILD`
- `WIRE`
- `VALIDATE`
- `REVIEW`

## Operating rules
- **Plan first**: changes touching more than two files must start with a written plan in `PLANS.md` or `docs/review-actions/`.
- **No hidden behavior**: all execution rules must be explicit in governed markdown.
- **No deep reference chains**: keep required behavior understandable within one reference level.
- **No unrelated refactors**: keep changes in declared scope.
- **Governed ownership admission**: new governed runtime/script paths must be validated by `scripts/validate_governed_runtime_ownership.py` with either a 3-letter owner or explicit support-only classification.

## Terminology normalization
Use these terms consistently:
- **execution**
- **artifact**
- **failure**
- **retrieve**

## Roadmap authority
Only `docs/roadmaps/system_roadmap.md` is authoritative for implementation sequencing.
