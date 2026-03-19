# Artifact Lineage System (Prompt BS)

## Overview

The Artifact Lineage System provides a strict, deterministic lineage graph that connects all pipeline artifacts with full traceability and integrity enforcement.

Every artifact can be traced back to its simulation input origin and evaluated for lineage correctness.

---

## Full Pipeline Lineage Diagram

```
simulation_input (depth 0)
    │
    ▼
simulation_output (depth 1)
    │
    ▼
evidence_pack (depth 2)
    │         ╲
    ▼          ▼
reasoning_trace (depth 3)
    │
    ▼
adversarial_result (depth 4)
    │         ╲
    ▼          ▼
synthesis ←──────────── (requires: evidence_pack + adversarial_result) (depth 5)
    │         ╲
    ▼          ▼
decision (depth 6) ──────────────────────────────┐
    │                                             │
    └──────────────────────────┐                 │
                               ▼                 │
                       slo_evaluation ←──────────┘
                       (requires: decision + synthesis) (depth 7)
```

### Required Parent Types

| Artifact Type | Required Parents |
|---|---|
| `simulation_input` | None (root) |
| `simulation_output` | `simulation_input` |
| `evidence_pack` | `simulation_output` |
| `reasoning_trace` | `evidence_pack` |
| `adversarial_result` | `reasoning_trace` |
| `synthesis` | `evidence_pack` **and** `adversarial_result` |
| `decision` | `synthesis` |
| `slo_evaluation` | `decision` **and** `synthesis` |

---

## Example Trace: simulation_input → decision → SLO

Given the following artifacts:

```json
{ "artifact_id": "SIM-IN-001", "artifact_type": "simulation_input", "lineage_depth": 0, "root_artifact_ids": ["SIM-IN-001"] }
{ "artifact_id": "SIM-OUT-001", "artifact_type": "simulation_output", "parent_artifact_ids": ["SIM-IN-001"], "lineage_depth": 1, "root_artifact_ids": ["SIM-IN-001"] }
{ "artifact_id": "EV-001", "artifact_type": "evidence_pack", "parent_artifact_ids": ["SIM-OUT-001"], "lineage_depth": 2, "root_artifact_ids": ["SIM-IN-001"] }
{ "artifact_id": "RT-001", "artifact_type": "reasoning_trace", "parent_artifact_ids": ["EV-001"], "lineage_depth": 3, "root_artifact_ids": ["SIM-IN-001"] }
{ "artifact_id": "ADV-001", "artifact_type": "adversarial_result", "parent_artifact_ids": ["RT-001"], "lineage_depth": 4, "root_artifact_ids": ["SIM-IN-001"] }
{ "artifact_id": "SYN-001", "artifact_type": "synthesis", "parent_artifact_ids": ["EV-001", "ADV-001"], "lineage_depth": 5, "root_artifact_ids": ["SIM-IN-001"] }
{ "artifact_id": "DEC-001", "artifact_type": "decision", "parent_artifact_ids": ["SYN-001"], "lineage_depth": 6, "root_artifact_ids": ["SIM-IN-001"] }
{ "artifact_id": "SLO-001", "artifact_type": "slo_evaluation", "parent_artifact_ids": ["DEC-001", "SYN-001"], "lineage_depth": 7, "root_artifact_ids": ["SIM-IN-001"] }
```

Tracing `SLO-001` to root:

```python
from spectrum_systems.modules.runtime.artifact_lineage import trace_to_root

path = trace_to_root("SLO-001", registry)
# ["SLO-001", "DEC-001", "SYN-001", "EV-001", "ADV-001", "RT-001", "SIM-OUT-001", "SIM-IN-001"]
```

This answers: **"Why was this SLO evaluation produced?"** — because decision `DEC-001` was made based on synthesis `SYN-001`, which was derived from evidence and adversarial results, all traceable to simulation input `SIM-IN-001`.

---

## Root Artifact Explanation

A **root artifact** is any artifact of type `simulation_input` — it has no parents and represents the entry point of the pipeline.

Every non-root artifact carries `root_artifact_ids`: a deduplicated list of all root ancestors reachable by recursively following `parent_artifact_ids`.

This field enables:
- Answering "What simulation(s) drove this decision?"
- Verifying that all downstream artifacts share a common origin.
- Detecting artifacts that have been disconnected from their simulation origin.

---

## Failure Modes

### Orphan Artifacts

An **orphan** is a non-root artifact with no `parent_artifact_ids`. Every artifact except `simulation_input` must have at least one parent.

**Detection:** `detect_lineage_gaps()` returns orphans in `gap_report.orphan_artifacts`.

**Enforcement:** `enforce_no_orphans()` raises `ValueError` if any orphan exists.

```
ERROR: Orphan non-root artifacts detected (must have ≥1 parent): ['EV-001']
```

### Broken Chains

A **broken chain** occurs when a parent referenced by `parent_artifact_ids` does not exist in the registry.

**Detection:** `detect_lineage_gaps()` returns broken references in `gap_report.missing_parents`.

**Enforcement:** `validate_lineage_chain()` returns `(False, errors)` listing the missing parent IDs.

```
ERROR: Artifact 'EV-001' references missing parents: ['SIM-OUT-MISSING']
```

### Circular Dependencies

A **circular dependency** occurs when an artifact appears in its own ancestor chain (directly or transitively).

**Detection:** `validate_lineage_chain()` uses depth-first traversal to detect cycles before they cause infinite recursion.

```
ERROR: Artifact 'A' is part of a circular dependency.
```

The system also uses a visited-set guard in `compute_root_artifacts()` to ensure cycle safety.

### Wrong Parent Types

Each artifact type requires specific parent types. For example, `synthesis` must have both an `evidence_pack` parent and an `adversarial_result` parent. Missing any required type is a hard failure.

```
ERROR: Artifact 'SYN-001' of type 'synthesis' must have a parent of type
       'adversarial_result' but none found.
```

### Inconsistent Lineage Depth

`lineage_depth` must equal `max(parent lineage_depth) + 1`. Inconsistencies indicate that metadata was corrupted or computed incorrectly.

**Detection:** `detect_lineage_gaps()` returns inconsistencies in `gap_report.depth_inconsistencies`.

---

## How Lineage Enforces Decision Defensibility

The lineage system makes every decision artifact **auditable**:

1. **Traceability**: `trace_to_root("DEC-001", registry)` returns the full chain back to the simulation input. Any reviewer can see exactly which simulation drove the decision.

2. **Integrity**: `validate_full_registry(registry)` checks every artifact in the chain for structural correctness. A decision is only valid if its entire lineage chain passes validation.

3. **SLO Integration**: The `slo_evaluation` artifact includes `lineage_valid` (computed by `validate_lineage_chain`) and can contribute a `traceability_integrity_sli` to the SLO evaluation. If lineage is broken, the SLO layer blocks downstream execution.

4. **No Silent Failures**: `enforce_no_orphans()` and `link_artifacts()` raise hard errors rather than proceeding silently.

5. **Deterministic IDs**: All artifact IDs are pass-through (no random generation), ensuring identical inputs always produce identical lineage graphs.

---

## Module Reference

**File:** `spectrum_systems/modules/runtime/artifact_lineage.py`

| Function | Purpose |
|---|---|
| `create_artifact_metadata(...)` | Build metadata with auto-computed depth, root IDs, and lineage validity |
| `link_artifacts(parent_ids, child_id, registry)` | Assert all parents exist; raise on missing |
| `compute_lineage_depth(...)` | depth = max(parent_depth) + 1 |
| `compute_root_artifacts(...)` | Recursively walk to root; deduplicate; cycle-safe |
| `validate_lineage_chain(...)` | Full chain check: parents exist, no cycles, correct types |
| `build_full_lineage_graph(registry)` | Returns adjacency map (parent → children) |
| `trace_to_root(artifact_id, registry)` | Path from artifact back to root(s) |
| `trace_to_leaves(artifact_id, registry)` | All downstream artifacts |
| `detect_lineage_gaps(registry)` | Missing parents, broken chains, depth errors, orphans |
| `enforce_no_orphans(registry)` | Hard-fail if any non-root artifact is parentless |
| `validate_against_schema(artifact)` | JSON Schema 2020-12 compliance check |
| `validate_full_registry(registry)` | Validate all artifacts; return structured report |

**Schema:** `contracts/schemas/artifact_lineage.schema.json`

**CLI:** `scripts/run_lineage_validation.py --dir <artifacts_dir>`

---

## CLI Usage

```bash
python scripts/run_lineage_validation.py --dir artifacts/ --output outputs/lineage_validation.json
```

**Exit codes:**
- `0` — All artifacts valid
- `1` — Lineage errors (orphans, broken chains, wrong parent types, etc.)
- `2` — Schema errors (artifacts fail JSON Schema validation)

**Output format (`outputs/lineage_validation.json`):**
```json
{
  "summary": {
    "total_artifacts": 8,
    "valid": true,
    "lineage_errors": 0,
    "schema_errors": 0,
    "orphan_artifacts": 0,
    "missing_parent_refs": 0,
    "depth_inconsistencies": 0
  },
  "lineage_graph": { ... },
  "lineage_validation": { ... },
  "gap_report": { ... }
}
```
