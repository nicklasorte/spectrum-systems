# System Registry

The System Registry is the authoritative catalog for the spectrum ecosystem. It records every governed repository and system, clarifying identity, role, loop alignment, artifact behavior, and maturity state so governance, orchestration, and downstream engines have a single source of truth.

## Purpose
- Preserve a canonical record of systems, preventing the “mystery repo” problem as the ecosystem grows.
- Capture system identity, role, primary loop alignment, consumed/emitted artifacts, contract dependencies, and maturity levels in both human-readable and machine-readable forms.
- Serve as the control-plane reference for governance, orchestration, dependency analysis, compliance, and future advisor capabilities.

## Why this matters
- Avoids repo sprawl and drift by keeping a single, governed list of systems.
- Preserves system identity as names or implementations evolve.
- Enables future dependency graphs, compliance checks, and advisory logic to reason over a stable inventory.

## Machine-readable registry
- Source: `ecosystem/system-registry.json`
- Schema: `ecosystem/system-registry.schema.json`
- Maturity tracking: `ecosystem/maturity-tracker.json` (schema in `ecosystem/maturity-tracker.schema.json`) with evidence and blockers aligned to `docs/level-0-to-20-playbook.md` and `docs/review-maturity-rubric.md`.
- Roadmap linkage: roadmap progress in `ecosystem/roadmap-tracker.json` should be cross-referenced with registry maturity levels to keep readiness and sequencing aligned.

## Development Runtime Standard
- All ecosystem repositories should adopt the base devcontainer defined in `devcontainer-spec/` within `spectrum-systems`.
- The standard runtime pins Python 3.11 and shared tooling to keep engines, pipelines, data lake utilities, and evaluation harnesses compatible.
- system-factory templates and downstream repos should inherit from this configuration to minimize environment drift and simplify onboarding.

## Current systems
| System ID | Repo | Type | Loop | Maturity | Status | Role |
| --- | --- | --- | --- | --- | --- | --- |
| spectrum-systems | `spectrum-systems` | governance | governance | 4 | active | Control plane for contracts, schemas, prompts, and governance standards. |
| spectrum-data-lake | `spectrum-data-lake` | data_lake | cross_loop | 5 | experimental | Governed storage, indexing, and lineage sidecars for ecosystem artifacts. |
| meeting-minutes-engine | `meeting-minutes-engine` | operational_engine | coordination | 5 | active | Transforms transcripts and agendas into governed meeting minutes and action capture. |
| working-paper-review-engine | `working-paper-review-engine` | operational_engine | document_production | 6 | active | Generates reviewer comment sets from governed working paper inputs. |
| comment-resolution-engine | `comment-resolution-engine` | operational_engine | document_production | 6 | active | Adjudicates reviewer comments and maintains governed resolution matrices. |
| docx-comment-injection-engine | `docx-comment-injection-engine` | operational_engine | document_production | 6 | active | Applies adjudicated comments into governed DOCX outputs with provenance. |
| spectrum-pipeline-engine | `spectrum-pipeline-engine` | orchestration | cross_loop | 7 | planned | Sequences governed engines, aligns contract versions, and emits pipeline manifests and readiness bundles. |
| spectrum-program-advisor | `spectrum-program-advisor` | advisory | cross_loop | 9 | experimental | Produces advisory briefs and next-best-action memos from readiness bundles and pipeline outputs. |
| system-factory | `system-factory` | factory | governance | 3 | active | Scaffolds new governed system repositories with pinned contracts and manifests. |

The registry is the canonical inventory for ecosystem alignment. New systems should be added here with clear artifact behavior and maturity placement before downstream adoption.
