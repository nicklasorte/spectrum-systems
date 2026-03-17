# Lifecycle Enforcement

This document describes the canonical artifact lifecycle enforced in spectrum-systems, the states and transitions defined in the control plane, and the enforcement rules every module must satisfy before advancing an artifact to the next stage.

---

## Lifecycle States

Lifecycle states are defined canonically in:

```
control_plane/lifecycle/lifecycle_states.json
```

| State | Label | Terminal |
|---|---|---|
| `input` | Input | No |
| `transformed` | Transformed | No |
| `evaluated` | Evaluated | No |
| `action_required` | Action Required | No |
| `in_progress` | In Progress | No |
| `resolved` | Resolved | No |
| `re_evaluated` | Re-evaluated | No |
| `closed` | Closed | **Yes** |

Every artifact must carry a `lifecycle_state` from this set. No artifact may exist without a `lifecycle_state`.

---

## Lifecycle Transitions

Valid state transitions are defined in:

```
control_plane/lifecycle/lifecycle_transitions.json
```

### Canonical Flow

```
input
  └─► transformed
        └─► evaluated
              ├─► action_required   (action_required = true)
              │     └─► in_progress
              │           └─► resolved
              │                 └─► re_evaluated
              │                       ├─► action_required  (loop)
              │                       └─► closed
              └─► closed             (action_required = false, rationale documented)
```

Any transition **not listed** in `lifecycle_transitions.json` is rejected by the lifecycle enforcer. Backward transitions and state skipping are not permitted.

### Required Fields per Transition

Each transition defines a set of required fields that must be present in the artifact **before the transition is permitted**:

| From | To | Required Fields |
|---|---|---|
| `input` | `transformed` | `artifact_id`, `artifact_type`, `module_origin`, `run_id` |
| `transformed` | `evaluated` | `artifact_id`, `artifact_type`, `run_id` |
| `evaluated` | `action_required` | `evaluation_id`, `action_required`, `linked_work_item_id` |
| `evaluated` | `closed` | `evaluation_id`, `action_required`, `rationale` |
| `action_required` | `in_progress` | `work_item_id`, `source_artifact_id` |
| `in_progress` | `resolved` | `work_item_id`, `resolution_notes` |
| `resolved` | `re_evaluated` | `artifact_id`, `artifact_type`, `run_id` |
| `re_evaluated` | `action_required` | `evaluation_id`, `action_required`, `linked_work_item_id` |
| `re_evaluated` | `closed` | `evaluation_id`, `action_required`, `rationale` |

---

## Lifecycle Enforcer

The central enforcement module is:

```
control_plane/lifecycle/lifecycle_enforcer.py
```

### Usage (Python)

```python
from control_plane.lifecycle.lifecycle_enforcer import LifecycleEnforcer, LifecycleViolationError

enforcer = LifecycleEnforcer()

# Validate a transition — raises LifecycleViolationError on failure
enforcer.validate_transition(artifact_dict, from_state="input", to_state="transformed")

# Query allowed next states
enforcer.allowed_next_states("evaluated")  # → ["action_required", "closed"]

# Check if a state is terminal
enforcer.is_terminal("closed")  # → True
```

### Usage (CLI)

```bash
python -m control_plane.lifecycle.lifecycle_enforcer \
  --artifact path/to/artifact.json \
  --from input \
  --to transformed
```

### Enforcement Rules

1. **No unknown states** — both `from_state` and `to_state` must be in `lifecycle_states.json`.
2. **No undefined transitions** — the `(from, to)` pair must appear in `lifecycle_transitions.json`.
3. **Required fields must be populated** — every field listed in the transition's `required_fields` must be present and non-empty in the artifact before the transition is allowed.
4. **`False` boolean values are treated as present** — boolean fields such as `action_required` with value `False` satisfy field presence checks.

---

## Enforcement Hooks

Before any lifecycle state change:

1. Call `LifecycleEnforcer.validate_transition(artifact, from_state, to_state)`.
2. If the call raises `LifecycleViolationError`, abort the state change and surface the error.
3. Only advance the `lifecycle_state` field after a successful validation.

Before artifact promotion (moving from `evaluated` → next state):

1. Validate that an evaluation result exists (`validate_artifact_has_evaluation`).
2. If `action_required = True`, validate that a work item exists (`validate_action_required_has_work_item`).

---

## Relationship to Data Backbone

The lifecycle enforcer operates on the artifact records described in the [Data Backbone](./data-backbone.md). Every artifact traveling through the lifecycle must have:

- An **artifact metadata** record in `data/artifacts/`
- A **lineage record** in `data/lineage/`
- An **evaluation result** in `data/evaluations/` before advancing past `transformed`
- A **work item** in `data/work_items/` when `action_required = True`

See `shared/adapters/artifact_emitter.py` for the helper functions that produce and validate these records.
