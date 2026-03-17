# Orchestration Ownership

**Status:** Canonical  
**Date:** 2026-03-17  
**Scope:** Platform-wide — all modules in `workflow_modules/`, `domain_modules/`, `control_plane/`, `shared/`, and `orchestration/`

---

## Purpose

This document defines who owns cross-module execution flow and artifact routing inside the spectrum-systems platform.  Ownership is exclusive and enforced by CI.  No ambiguity is permitted.

---

## 1. Orchestration owns cross-module flow

`orchestration/` is the **sole** owner of:

| Responsibility | Owned by |
|---|---|
| Module execution order | `orchestration/` |
| Cross-module artifact routing | `orchestration/` |
| Artifact handoff sequencing | `orchestration/` |
| Lifecycle transition triggering (cross-module) | `orchestration/` |
| Cross-module dependency flow | `orchestration/` |

No other layer may define, invoke, or replicate these responsibilities.  Every cross-module artifact transfer must be described in an orchestration-flow manifest and carried over the canonical artifact bus.

---

## 2. What modules may and may not do

### `workflow_modules/` and `domain_modules/`

**May:**
- Define their own local processing logic
- Declare their `inputs` and `outputs` in their module manifest
- Depend on `shared/` primitives

**May NOT:**
- Define execution order for other modules
- Directly route artifacts to another module outside the artifact bus
- Embed cross-module routing metadata in their local schemas or manifests
- Define or instantiate orchestration-flow documents

### `control_plane/`

**May:**
- Validate lifecycle state transitions for governed artifacts
- Govern contract and schema conformance
- Emit governance findings and work items

**May NOT:**
- Own execution flow
- Define the sequence in which modules run
- Route artifacts between modules

### `shared/`

**May:**
- Define canonical primitives (artifact models, identifiers, lineage, provenance)
- Export schemas consumed by other modules

**May NOT:**
- Define or embed execution order
- Own artifact routing decisions

---

## 3. Artifact handoff rule

If a module needs another module's output, it must receive it via the **artifact bus** under an **orchestration contract**.

Direct module-to-module coupling — where a module hardcodes a reference to another module's internal path, output contract, or execution state — is a violation of this rule and will be flagged by the orchestration boundary validator.

The artifact bus schema is defined at:

```
schemas/artifact-bus-message.schema.json
```

Orchestration flows that describe how artifacts move between modules are defined at:

```
schemas/orchestration-flow.schema.json
docs/examples/orchestration-flow.example.json
```

---

## 4. Anti-patterns (forbidden behaviors)

The following patterns are explicitly forbidden and will fail CI validation.

### Anti-pattern 1 — Self-orchestration in a workflow module

```json
// workflow_modules/meeting_intelligence/local-flow.json  ← FORBIDDEN
{
  "next_module": "control_plane.evaluation",
  "execution_order": ["transcript_ingest", "minutes_draft", "forward_to_eval"]
}
```

**Rule violated:** `workflow_modules` must not define execution order for other modules or declare `next_module` routing.

---

### Anti-pattern 2 — Cross-module direct coupling

```python
# domain_modules/knowledge_capture/processor.py  ← FORBIDDEN
from workflow_modules.meeting_intelligence import output_contract
result = output_contract.fetch_latest()
```

**Rule violated:** Domain modules must not import from or directly couple to `workflow_modules`.  All inputs arrive via the artifact bus.

---

### Anti-pattern 3 — Orchestration-flow schema defined outside `orchestration/`

```
control_plane/lifecycle/orchestration-flow.schema.json  ← FORBIDDEN
```

**Rule violated:** Orchestration-flow documents are only valid under `orchestration/` or the canonical `schemas/` location.

---

### Anti-pattern 4 — Duplicated artifact-bus structures

```
workflow_modules/comment_resolution/artifact-bus-message.schema.json  ← FORBIDDEN
```

**Rule violated:** The artifact bus schema is canonical and lives at `schemas/artifact-bus-message.schema.json`.  Local copies are not permitted.

---

### Anti-pattern 5 — Control plane triggering module execution

```python
# control_plane/lifecycle/lifecycle_enforcer.py  ← FORBIDDEN
if artifact.state == "evaluated":
    workflow_modules.meeting_intelligence.run()
```

**Rule violated:** `control_plane/` validates and governs transitions; it does not trigger or sequence module execution.

---

## 5. Relationship to module manifests

Module manifests (under `docs/module-manifests/`) are the **source of truth for module capabilities**:

- `inputs` — what artifact types a module accepts
- `outputs` — what artifact types a module produces
- `forbidden_responsibilities` — what a module explicitly does not own

Orchestration flows and artifact-bus messages must be validated against these manifests:

- A target module cannot receive an artifact type it did not declare as an `input` in its manifest
- Orchestration flows must only reference `module_id` values that exist in a manifest
- The artifact bus `source_module` and `target_module` fields must resolve to real module manifests

This ensures capabilities and flow are always consistent, and that modules declare what they can accept before orchestration wires them together.

---

## 6. Enforcement

| Check | Enforced by | CI job |
|---|---|---|
| No orchestration-flow files in non-orchestration modules | `scripts/validate_orchestration_boundaries.py` | `validate-orchestration-boundaries` |
| No cross-module routing metadata in non-orchestration modules | `scripts/validate_orchestration_boundaries.py` | `validate-orchestration-boundaries` |
| No duplicated artifact-bus schemas | `scripts/validate_orchestration_boundaries.py` | `validate-orchestration-boundaries` |
| Artifact-bus messages conform to schema | `scripts/validate_orchestration_boundaries.py` | `validate-artifact-bus-schema` |
| Source/target modules exist in manifests | `scripts/validate_orchestration_boundaries.py` | `validate-artifact-bus-schema` |
| Target module declares artifact type as input | `scripts/validate_orchestration_boundaries.py` | `validate-artifact-bus-schema` |
| Orchestration flows conform to schema | `scripts/validate_orchestration_boundaries.py` | `validate-orchestration-boundaries` |

---

## See also

- `docs/architecture/artifact-bus.md` — canonical artifact bus model
- `schemas/artifact-bus-message.schema.json` — artifact bus message schema
- `schemas/orchestration-flow.schema.json` — orchestration flow schema
- `docs/architecture/module-pivot-roadmap.md` — platform architecture context
- `docs/architecture/data-backbone.md` — data backbone context
