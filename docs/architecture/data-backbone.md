# Data Backbone

This document describes the canonical data schemas, emitter utilities, and persistence structure that form the spectrum-systems data backbone. Every module producing a governed artifact must emit the required data records described here.

---

## Overview

The data backbone ensures that every artifact in the ecosystem is:

- **Identifiable** — carries a canonical metadata record
- **Traceable** — has a lineage record linking it to its parents and producing module
- **Evaluated** — has an evaluation result (or an explicit pending marker) before promotion
- **Actionable** — if evaluation requires action, a work item exists and is linked

---

## Canonical Schemas

All schemas live under:

```
shared/
  artifact_models/   artifact_metadata.schema.json
  lineage/           lineage.schema.json
  evaluation/        evaluation_result.schema.json
  work_items/        work_item.schema.json
```

### 1. Artifact Metadata (`artifact_metadata.schema.json`)

Every artifact must have a metadata record emitted by the producing module.

| Field | Type | Required | Description |
|---|---|---|---|
| `artifact_id` | string | ✓ | Stable unique identifier |
| `artifact_type` | string | ✓ | Canonical type name |
| `module_origin` | string | ✓ | Engine/module that produced it |
| `created_at` | datetime | ✓ | ISO 8601 creation timestamp |
| `lifecycle_state` | enum | ✓ | Current lifecycle state |
| `contract_version` | semver | ✓ | Governing contract version |
| `schema_version` | semver | ✓ | Metadata schema version |
| `run_id` | string | — | Correlating pipeline run ID |

### 2. Lineage Record (`lineage.schema.json`)

Captures the provenance chain for an artifact.

| Field | Type | Required | Description |
|---|---|---|---|
| `artifact_id` | string | ✓ | Artifact whose lineage this describes |
| `parent_artifacts` | list[string] | ✓ | Parent artifact IDs (empty for root) |
| `producing_module` | string | ✓ | Module that produced the artifact |
| `run_id` | string | ✓ | Run that produced the artifact |
| `timestamp` | datetime | ✓ | When the lineage record was emitted |

### 3. Evaluation Result (`evaluation_result.schema.json`)

Records the outcome of evaluation. Must be emitted (or marked pending) before an artifact may be promoted.

| Field | Type | Required | Description |
|---|---|---|---|
| `evaluation_id` | string | ✓ | Unique evaluation identifier |
| `artifact_id` | string | ✓ | Evaluated artifact |
| `status` | enum | ✓ | `pass` / `fail` / `partial` |
| `action_required` | boolean | ✓ | Whether a work item is required |
| `rationale` | string | ✓ | Explanation of outcome |
| `linked_work_item_id` | string\|null | — | Required (non-null) when `action_required=true` |

### 4. Work Item (`work_item.schema.json`)

Lightweight tracking record for required remediation.

| Field | Type | Required | Description |
|---|---|---|---|
| `work_item_id` | string | ✓ | Unique work item ID |
| `source_artifact_id` | string | ✓ | Evaluation that triggered this item |
| `status` | enum | ✓ | `open` / `in_progress` / `resolved` / `deferred` |
| `priority` | enum | ✓ | `critical` / `high` / `medium` / `low` |
| `created_at` | datetime | ✓ | Creation timestamp |
| `resolution_notes` | string | — | Required when `status=resolved` |

---

## Shared Emitter Utility

All modules must use the helpers in:

```
shared/adapters/artifact_emitter.py
```

### Factory Functions

```python
from shared.adapters.artifact_emitter import (
    create_artifact_metadata,
    create_lineage_record,
    create_evaluation_result,
    create_work_item,
)

meta = create_artifact_metadata(
    artifact_id="ARTIFACT-001",
    artifact_type="engine_output",
    module_origin="my-engine",
    lifecycle_state="input",
    contract_version="1.0.0",
)

lineage = create_lineage_record(
    artifact_id="ARTIFACT-001",
    parent_artifacts=[],
    producing_module="my-engine",
    run_id="run-2026-001",
)

eval_result = create_evaluation_result(
    artifact_id="ARTIFACT-001",
    status="pass",
    action_required=False,
    rationale="All criteria met.",
)
```

Each factory function **validates its inputs** and raises `ValueError` on constraint violations.

### Enforcement Helpers

```python
from shared.adapters.artifact_emitter import (
    validate_artifact_has_metadata,
    validate_artifact_has_lineage,
    validate_artifact_has_evaluation,
    validate_action_required_has_work_item,
)

# Fail fast if any required record is absent
validate_artifact_has_metadata("ARTIFACT-001")
validate_artifact_has_lineage("ARTIFACT-001")
validate_artifact_has_evaluation("ARTIFACT-001")
validate_action_required_has_work_item(eval_result)
```

These helpers raise `ValueError` immediately when a required record is absent.

---

## Persistence / Storage

Records are stored as JSON files under:

```
data/
  artifacts/     ← artifact metadata records
  lineage/       ← lineage records
  evaluations/   ← evaluation results
  work_items/    ← work item records
```

Each record is stored as `<record_id>.json`.

### Persistence Helpers

```python
from shared.adapters.artifact_emitter import save_artifact_record, load_artifact_record

# Persist a record
save_artifact_record("artifacts", "ARTIFACT-001", meta)

# Load a record
loaded = load_artifact_record("artifacts", "ARTIFACT-001")
```

---

## Enforcement Rules

| Rule | Enforcement |
|---|---|
| No artifact without metadata | `validate_artifact_has_metadata` |
| No artifact without lineage | `validate_artifact_has_lineage` |
| No promotion without evaluation | `validate_artifact_has_evaluation` |
| `action_required=True` → work item must exist | `validate_action_required_has_work_item` |
| `action_required=False` → rationale must be non-empty | enforced in `create_evaluation_result` |
| Lifecycle transition must be valid | `LifecycleEnforcer.validate_transition` |

All rules **fail fast and explicitly** — they raise exceptions with descriptive messages rather than silently allowing invalid states.

---

## Relationship to Lifecycle Enforcement

The data backbone is the substrate on which lifecycle enforcement operates. See [Lifecycle Enforcement](./lifecycle-enforcement.md) for:

- Lifecycle state definitions
- Valid transition rules
- Required fields per transition
- The `LifecycleEnforcer` module
