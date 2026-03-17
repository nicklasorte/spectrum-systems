# Artifact Lifecycle

This document defines the canonical lifecycle for governed artifacts in the spectrum-systems ecosystem. Every artifact produced by an engine, pipeline, or review process must travel through defined stages, with explicit ownership, expected outputs, and transition triggers at each stage.

---

## Lifecycle Stages

```
input →
  transformation →
    evaluation →
      work item generation →
        resolution →
          re-evaluation
```

---

## Stage Definitions

### 1. Input

**What it is:** Raw or upstream artifacts consumed by a governed engine or pipeline.

**Repo ownership:** Upstream system repos (e.g., spectrum-pipeline-engine) or external data sources defined in `DATA_SOURCES.md`.

**Expected artifacts:**
- External artifact manifests (`contracts/schemas/external_artifact_manifest.schema.json`)
- Working paper inputs (`contracts/schemas/working_paper_input.schema.json`)
- Meeting agenda contracts (`contracts/schemas/meeting_agenda_contract.schema.json`)

**Transition trigger:** Input validated against its governing schema; run manifest emitted with `run_id`.

---

### 2. Transformation

**What it is:** A governed engine processes the input and produces a structured output artifact.

**Repo ownership:** Operational engine repos (e.g., comment-resolution-engine, meeting-minutes-engine).

**Expected artifacts:**
- Engine output artifact (e.g., comment resolution matrix, meeting minutes record)
- Run manifest (`governance/schemas/run_manifest.schema.json`)
- Provenance record (`contracts/schemas/provenance_record.schema.json`)

**Transition trigger:** Engine completes run; run manifest and provenance record emitted with correlated `run_id`. Contract validation report generated.

---

### 3. Evaluation

**What it is:** The output artifact is evaluated against governed criteria. Every evaluation MUST produce a definitive outcome: `action_required = true` or `action_required = false`.

**Repo ownership:** spectrum-systems (schema authority); spectrum-pipeline-engine (evaluation runner).

**Expected artifacts:**
- Evaluation manifest (`contracts/schemas/evaluation_manifest.schema.json`) with fields:
  - `evaluation_id` (the `artifact_id` field)
  - `status`: `pass` | `fail` | `partial` | `warning` | `not-yet-evaluable`
  - `action_required`: boolean — **required on every evaluation**
  - `linked_work_item_id`: string | null — required when `action_required = true`
  - `rationale`: string — required when `action_required = false`

**Contract rules (enforced by `scripts/validate_evaluation_contract.py`):**
- Every evaluation result MUST have `action_required`.
- `action_required = true` → `linked_work_item_id` must be set.
- `action_required = false` → `rationale` must explain why no action is needed.

**Transition trigger:** Evaluation manifest written and validated. If `action_required = true`, proceed to Work Item Generation. If `action_required = false`, record closes with rationale; lifecycle may skip to Re-evaluation on next run.

---

### 4. Work Item Generation

**What it is:** A structured work item is created to track any required action identified during evaluation.

**Repo ownership:** spectrum-systems (work item schema authority); upstream reviews and evaluations supply source material.

**Expected artifacts:**
- Work item (`schemas/work-item.schema.json`) with:
  - `source_type`: `evaluation` (for evaluation-driven items) or `review`
  - `source_id`: the `artifact_id` of the originating evaluation manifest
  - `linked_evaluation_id`: the `artifact_id` of the evaluation manifest

**Transition trigger:** Work item created; `evaluation_manifest.linked_work_item_id` updated with the new work item ID. Work item written to `governance/work-items/work-items.json`.

---

### 5. Resolution

**What it is:** The work item is addressed — either by implementing a fix, accepting the risk, or deferring.

**Repo ownership:** Responsible operational engine repo or spectrum-systems for governance-level items.

**Expected artifacts:**
- Updated work item with `status`: `resolved` | `deferred`
- PR or commit reference in work item `resolution_notes`
- Updated evaluation manifest or new evaluation manifest confirming closure

**Transition trigger:** Work item status updated to `resolved` or `deferred`; linked evaluation noted.

---

### 6. Re-evaluation

**What it is:** After resolution, the artifact or system is re-evaluated to confirm the issue is addressed.

**Repo ownership:** spectrum-systems (evaluation criteria); spectrum-pipeline-engine (re-run).

**Expected artifacts:**
- New evaluation manifest with `status: pass` (ideally) and `action_required: false` with rationale documenting the resolution.
- Evidence bundle correlated to the same `run_id` as the resolution.

**Transition trigger:** Re-evaluation passes; lifecycle record closed. If re-evaluation fails, a new work item is generated and the loop continues.

---

## Lifecycle Diagram

```
┌─────────┐      ┌────────────────┐      ┌────────────┐
│  Input  │ ───► │ Transformation │ ───► │ Evaluation │
└─────────┘      └────────────────┘      └────────────┘
                                               │
                           ┌───────────────────┤
                           │ action_required?  │
                           │                   │
                  true ────┘           false ──┘
                    │                    │
                    ▼                    ▼
          ┌─────────────────┐    ┌──────────────────┐
          │ Work Item Gen.  │    │ Record rationale  │
          └─────────────────┘    │ (no action taken) │
                    │            └──────────────────┘
                    ▼
          ┌─────────────────┐
          │   Resolution    │
          └─────────────────┘
                    │
                    ▼
          ┌─────────────────┐
          │  Re-evaluation  │ ───► (loops back to Evaluation)
          └─────────────────┘
```

---

## Repo Ownership Summary

| Stage               | Schema Authority       | Runner / Producer                          |
|---------------------|------------------------|--------------------------------------------|
| Input               | spectrum-systems       | Upstream engines / external sources        |
| Transformation      | spectrum-systems       | Operational engine repos                   |
| Evaluation          | spectrum-systems       | spectrum-pipeline-engine                   |
| Work Item Gen.      | spectrum-systems       | scripts/generate_work_items.py             |
| Resolution          | Operational repo       | Responsible engineer or agent              |
| Re-evaluation       | spectrum-systems       | spectrum-pipeline-engine                   |

---

## Alignment with Pipeline Expectations

- The `run_id` field must be consistent across all artifacts in a single lifecycle pass (run manifest, provenance, evaluation manifest, contract validation report).
- Evaluation manifests that set `action_required = true` are consumed by `scripts/generate_work_items.py` to produce work items in `governance/work-items/`.
- Review artifacts (from Claude or human reviewers) that identify issues should produce an evaluation manifest before entering the work item stage.
- See `docs/run-evidence-correlation-rule.md` for the correlated evidence bundle rule.
- See `contracts/schemas/evaluation_manifest.schema.json` for the evaluation output contract.
- See `schemas/work-item.schema.json` for the work item schema.
- See `schemas/review-artifact.schema.json` for the canonical review artifact schema.

---

## Validation Scripts

| Script                                        | Purpose                                              |
|-----------------------------------------------|------------------------------------------------------|
| `scripts/validate_evaluation_manifest.py`     | JSON Schema + evidence-ref integrity checks          |
| `scripts/validate_evaluation_contract.py`     | Control-loop contract (action_required linkage)      |
| `scripts/validate_review_artifacts.py`        | Review artifact JSON Schema validation               |
| `scripts/generate_work_items.py`              | Generates work items from review and evaluation data |

---

_Last updated: 2026-03-17_
