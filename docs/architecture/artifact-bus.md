# Artifact Bus

**Status:** Canonical  
**Date:** 2026-03-17  
**Scope:** Platform-wide — all cross-module artifact transfers

---

## What the artifact bus is

The artifact bus is the canonical channel through which modules exchange artifacts inside the spectrum-systems platform.

Every cross-module artifact transfer must be routed through the artifact bus.  A module that receives an artifact must receive it as an artifact bus message — not as a direct import, function call, or bespoke handoff.

The artifact bus is owned and operated by the orchestration layer (`orchestration/`).  Modules do not directly address each other; they declare inputs and outputs, and the orchestration layer wires them together via artifact bus messages.

---

## When the artifact bus is used

The artifact bus is used whenever:

1. A module produces an artifact that another module must consume
2. An artifact transitions from one lifecycle state to another across a module boundary
3. An orchestration flow advances from one stage to the next
4. An evaluation outcome triggers an artifact transfer (e.g., `action_required` → work item)
5. A cross-module review or resolution path is triggered

The artifact bus is **not** used for:

- Module-internal processing (within a single module's boundary)
- `shared/` primitive lookups (those are static schema imports)
- Control plane lifecycle validation calls (those happen on the same artifact, not a transfer)

---

## Required fields

Every artifact bus message must include all required fields defined in:

```
schemas/artifact-bus-message.schema.json
```

| Field | Purpose |
|---|---|
| `message_id` | Unique identifier for this bus message (`MSG-*`) |
| `artifact_id` | Identifier of the artifact being transferred (`ART-*`) |
| `artifact_type` | Canonical artifact type; must match the target module's declared `inputs` |
| `source_module` | `module_id` of the emitting module; must resolve to a real manifest |
| `target_module` | `module_id` of the receiving module; must resolve to a real manifest |
| `lifecycle_state` | Artifact state at handoff; must be valid per `lifecycle_states.json` |
| `payload_ref` | Pointer to the artifact payload (envelope ID, storage reference) |
| `contract_version` | Semver version of the artifact contract governing this type |
| `schema_version` | Version of the artifact-bus-message schema (currently `1.0.0`) |
| `timestamp` | UTC ISO-8601 timestamp when the message was emitted |
| `run_id` | Orchestration run identifier (`RUN-*`); links to the pipeline run manifest |
| `lineage_ref` | Lineage record ID (`LIN-*`); required for all governed handoffs |

Optional fields (`evaluation_ref`, `work_item_ref`, `metadata`) may be included when the transfer is linked to an evaluation outcome or work item.

---

## Relationship to lifecycle states

The `lifecycle_state` field in an artifact bus message must reflect the **current state of the artifact at the time of handoff**.

Valid states are defined in `control_plane/lifecycle/lifecycle_states.json`.  Artifact bus messages carrying an artifact in an unrecognized state will fail validation.

Typical states at handoff:

| State | Meaning at handoff |
|---|---|
| `transformed` | A workflow or domain module produced the artifact; ready for evaluation |
| `evaluated` | The artifact has been evaluated; ready for work-item or resolution routing |
| `action_required` | Evaluation requires follow-up; `work_item_ref` must be present |
| `in_progress` | Work item has been opened; artifact is under active resolution |

---

## Relationship to lineage

Every governed artifact bus message must include a `lineage_ref` that points to a lineage record.

The lineage record provides the full chain of custody:
- Source artifact(s) that contributed to this artifact
- Module that produced the artifact
- Run that triggered the production
- Human review checkpoints where applicable

Lineage schema: `shared/lineage/lineage.schema.json`

---

## Relationship to evaluation

When an artifact bus message results from an evaluation outcome, it should include an `evaluation_ref` pointing to the evaluation result.

If the evaluation set `action_required: true`, the message must also include a `work_item_ref`.

This links the bus message to the full evaluation → work-item control loop.

---

## Relationship to module manifests

Artifact bus messages are validated against module manifests:

1. `source_module` must match a `module_id` in an existing manifest
2. `target_module` must match a `module_id` in an existing manifest
3. `artifact_type` must appear in the `target_module`'s manifest `inputs` list

If any of these checks fail, the handoff is rejected.  This ensures modules only receive artifact types they have declared capability to handle.

---

## Relationship to orchestration flows

Artifact bus messages are emitted as part of orchestration flows.  An orchestration flow document (schema: `schemas/orchestration-flow.schema.json`) describes:

- Which modules participate in a flow
- What artifact types are transferred
- What lifecycle states are valid at each stage
- What validations are required before a transfer proceeds

Artifact bus messages reference the `run_id` of the originating orchestration flow execution.

---

## Example

```json
{
  "schema_version": "1.0.0",
  "message_id": "MSG-MEET-001.EVAL-001",
  "artifact_id": "ART-MINUTES-2026-0317-001",
  "artifact_type": "MeetingMinutesRecord",
  "source_module": "workflow_modules.meeting_intelligence",
  "target_module": "control_plane.evaluation",
  "lifecycle_state": "transformed",
  "payload_ref": "ART-MINUTES-2026-0317-001",
  "contract_version": "1.0.0",
  "timestamp": "2026-03-17T14:00:00Z",
  "run_id": "RUN-MEET-EVAL-2026-0317-001",
  "lineage_ref": "LIN-MINUTES-2026-0317-001"
}
```

Full example: `docs/examples/artifact-bus-message.example.json`

---

## See also

- `docs/architecture/orchestration-ownership.md` — who owns cross-module flow
- `schemas/artifact-bus-message.schema.json` — canonical schema
- `schemas/orchestration-flow.schema.json` — orchestration flow schema
- `control_plane/lifecycle/lifecycle_states.json` — valid lifecycle states
- `shared/lineage/lineage.schema.json` — lineage schema
