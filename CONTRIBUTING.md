# Contributing Guide

## Purpose
This repository is a system design lab notebook. Contributions should focus on architecture, workflows, schemas, and design reasoning rather than production code.

## Contribution Types
Allowed contributions include:
- proposing new automation systems
- improving bottleneck analysis
- expanding schema definitions
- improving data lake strategy
- clarifying provenance requirements
- improving documentation clarity

## Process for Proposing a New System
1. Identify the bottleneck addressed.
2. Add the system to SYSTEMS.md.
3. Add details to docs/systems-registry.md.
4. Define required inputs and outputs.
5. Define required schemas and provenance metadata.

## Process for Updating Schemas
All schema updates must:
- follow the Data Provenance Standard
- maintain backwards compatibility when possible
- include clear field descriptions

## Resolving Merge Conflicts in Generated Artifacts
Run-specific generated artifacts (for example
`artifacts/certification_judgment_40_explicit/*.json`,
`artifacts/pqx_runs/**/*.json`) embed timestamps and trace IDs that diverge
between branches. **Do not hand-merge these files.** Regenerate them by running
the script declared in `config/generated_artifact_policy.json` and commit the
deterministic output. See `docs/generated-artifact-merge-policy.md`.

After cloning, run `bash scripts/install_hooks.sh` to register the
`generated-artifact` Git merge driver and the pre-push guard.

## Agent Workflow
- Claude → reasoning and architecture
- Codex → repository changes
- Copilot → code implementation in downstream repos
