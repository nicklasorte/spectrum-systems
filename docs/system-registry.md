# System Registry (Ecosystem Companion)

This document is a companion surface for ecosystem orientation. It is **not** the canonical authority for subsystem ownership.

## Authority
- Canonical authority for system names, acronyms, ownership, and placeholder status: `docs/architecture/system_registry.md`.
- Machine-readable ecosystem inventory: `ecosystem/system-registry.json` (schema: `ecosystem/system-registry.schema.json`).
- This file summarizes ecosystem-facing repository inventory and defers ownership decisions to the canonical registry.

## Purpose
- Provide a concise ecosystem inventory view for operators.
- Link machine-readable inventory artifacts used by tooling.
- Avoid duplicating ownership definitions already governed by the canonical registry.

## Machine-readable companion artifacts
- Registry: `ecosystem/system-registry.json`
- Schema: `ecosystem/system-registry.schema.json`
- Maturity tracker: `ecosystem/maturity-tracker.json` (schema: `ecosystem/maturity-tracker.schema.json`)
- Roadmap tracker: `ecosystem/roadmap-tracker.json`

## Repository inventory (companion summary)
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

For ownership conflicts, treat this file as derived and correct the derived surface to match `docs/architecture/system_registry.md`.
