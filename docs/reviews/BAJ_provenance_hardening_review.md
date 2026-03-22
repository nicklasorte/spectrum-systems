# BAJ Provenance Hardening — Trust & Traceability Audit

---

## Metadata

| Field             | Value                                        |
|-------------------|----------------------------------------------|
| **Review date**   | 2026-03-22                                   |
| **Reviewer**      | Claude (Anthropic, claude-sonnet-4-6)        |
| **Branch**        | `claude/audit-baj-provenance-cvTD6`          |
| **Scope**         | BAJ Provenance Hardening layer               |
| **Review type**   | Forensic audit — fail-closed                 |
| **Decision**      | **FAIL**                                     |

---

## Scope

Files examined in full:

| File | Role |
|------|------|
| `governance/schemas/provenance.schema.json` | Operational provenance schema |
| `schemas/provenance-schema.json` | Reusable provenance schema |
| `contracts/schemas/provenance_record.schema.json` | Contract provenance record schema |
| `contracts/standards-manifest.json` | Standards manifest |
| `spectrum_systems/study_runner/artifact_writer.py` | Study compiler artifact emission |
| `shared/adapters/artifact_emitter.py` | Shared artifact metadata factory |
| `spectrum_systems/modules/strategic_knowledge/provenance.py` | Strategic knowledge provenance helpers |
| `spectrum_systems/modules/runtime/enforcement_engine.py` | BAF enforcement engine |
| `spectrum_systems/modules/runtime/artifact_lineage.py` | Artifact lineage system |
| `spectrum_systems/modules/runtime/trace_engine.py` | Trace / span engine |
| `spectrum_systems/modules/runtime/policy_registry.py` | SLO policy registry |
| `governance/examples/evidence-bundle/provenance.json` | Canonical governance example |
| `contracts/examples/provenance_record.json` | Canonical contract example |

---

## Decision

### FAIL

The provenance layer contains five distinct structural failures. Any one of them independently produces artifacts that cannot be audited, replayed, or forensically verified. Together they represent a pervasive gap between the declared governance model and what the system actually emits at runtime.

---

## Critical Findings

### Finding 1 — Trace context is entirely absent from study runner provenance

**Files:** `spectrum_systems/study_runner/artifact_writer.py:36–51` and `spectrum_systems/modules/runtime/trace_engine.py`

**Finding:**

The `_provenance_record()` function in `artifact_writer.py` is the sole provenance emission point for all study compiler outputs (tables, figures, study summary, results). It emits the following fields:

```
record_id, record_type, source_document, source_revision,
workflow_name, workflow_step, generated_by_system,
generated_by_repo, generated_by_version, policy_id,
schema_version, created_at, updated_at
```

There is no `trace_id`, no `span_id`, no trace reference of any kind. The trace engine (`trace_engine.py`) is a completely separate subsystem providing `start_trace()`, `start_span()`, `attach_artifact()`, and `validate_trace_context()`. There is no call to any of these functions anywhere in `artifact_writer.py`. The two systems are structurally decoupled.

**Why this is dangerous:**

Every artifact emitted by the study compiler — results.json, study_summary.json, all CSV tables, all figure metadata — exists in a forensic vacuum with respect to the distributed trace. There is no handle to the trace context under which the artifact was produced.

**How it fails in a real scenario:**

An investigator receives a study summary artifact and wants to replay the exact execution that produced it. The artifact has a `run_id` but no `trace_id`. The run_id alone cannot reconstruct: which spans executed, what events were recorded, what enforcement decisions were made, or whether any span ended with `status: "error"` that was silently absorbed. The trace engine records all of this — but it is unreachable from the artifact. The audit trail is broken.

---

### Finding 2 — Primary artifact metadata factory omits `policy_id` entirely

**File:** `shared/adapters/artifact_emitter.py:72–107`

**Finding:**

`create_artifact_metadata()` is the canonical shared factory that every governed module is instructed to use for artifact emission. Its signature is:

```python
def create_artifact_metadata(
    *,
    artifact_id: str,
    artifact_type: str,
    module_origin: str,
    lifecycle_state: str,
    contract_version: str,
    schema_version: str = "1.0.0",
    run_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
```

There is no `policy_id` parameter. The function has no mechanism to accept, validate, or record a policy identifier. The returned dict contains eight fields, none of which is `policy_id`.

Both provenance schemas that govern this layer (`governance/schemas/provenance.schema.json` and `schemas/provenance-schema.json`) declare `policy_id` as a required field with a strict semantic-version pattern: `^[a-z][a-z0-9-]*-v\d+\.\d+\.\d+$`.

**Why this is dangerous:**

Any module that follows the documented usage pattern — calling `create_artifact_metadata()` as directed in the module docstring — will produce an artifact with no policy linkage regardless of how carefully it follows all other requirements. The shared emitter, which is explicitly the single point of canonical artifact metadata creation, systematically drops the most critical governance binding field.

**How it fails in a real scenario:**

Module A produces an artifact using `create_artifact_metadata()`. The artifact passes internal validation because `create_artifact_metadata()` does not validate against the provenance schemas. The artifact is stored and later submitted to a governance audit pipeline that validates against `schemas/provenance-schema.json`. The artifact fails validation on `policy_id: required`. The artifact has no `policy_id` to inject retroactively, because the originating run context has ended. The artifact is ungovernable.

---

### Finding 3 — Strategic knowledge artifacts emit a schema-free shadow provenance model

**File:** `spectrum_systems/modules/strategic_knowledge/provenance.py:13–20`

**Finding:**

The `build_provenance()` function used for all strategic knowledge artifact families emits:

```python
def build_provenance(*, extraction_run_id: str, extractor_version: str, notes: str | None = None) -> dict:
    provenance = {
        "extraction_run_id": extraction_run_id,
        "extractor_version": extractor_version,
    }
    if notes:
        provenance["notes"] = notes
    return provenance
```

This function produces a dict with two required fields and one optional field. Absent from the output:

- `policy_id` (required by both provenance schemas)
- `contract_version` (required by `governance/schemas/provenance.schema.json`)
- `commit_sha` (required by `governance/schemas/provenance.schema.json`)
- `trace_id` / `span_id` (no trace linkage)
- `record_id` (required pattern `^PRV-[A-Z0-9._-]+$`)
- `schema_version`
- `source_revision`
- `workflow_name` / `workflow_step`
- `generated_by_system` / `generated_by_repo`

There is no call to `jsonschema` or any schema validator in this module. The function performs no validation whatsoever. An artifact calling `build_provenance()` can truthfully say it called the provenance helper and received a provenance dict — and still have produced something that fails every applicable governance schema.

**Why this is dangerous:**

This is a structurally parallel provenance system that bypasses the governance layer entirely. Any number of strategic knowledge artifacts can exist with completely opaque provenance — no policy linkage, no trace context, no schema version, no record identity — while the system believes it has handled provenance correctly because `build_provenance()` returned a non-empty dict.

**How it fails in a real scenario:**

A strategic knowledge extraction run produces 50 artifacts, each with provenance created by `build_provenance()`. A compliance audit requests all artifacts with their governing `policy_id`. The artifacts have no `policy_id`. There is no way to determine what policy governed their extraction, what version of the extractor ran, or what trace context they were produced under. The artifacts are forensically opaque. Their lineage cannot be reconstructed.

---

### Finding 4 — Static hardcoded fields in `artifact_writer.py` make replay reconstruction impossible

**File:** `spectrum_systems/study_runner/artifact_writer.py:41, 46, 47`

**Finding:**

The `_provenance_record()` function contains three fields that are burned-in static string literals:

```python
"source_revision": "rev0",                             # line 41
"generated_by_version": "design-notebook",             # line 46
"policy_id": "study-output-governance-v1.0.0",         # line 47
```

None of these values are derived from runtime state:

- `source_revision: "rev0"` — hardcoded to revision zero regardless of what revision of the source study config document was actually used. Every run at every point in time claims to have been produced from revision 0 of the source. If the source document has been updated, the provenance record still claims `rev0`.

- `generated_by_version: "design-notebook"` — a descriptive label, not a version identifier. The schema `schemas/provenance-schema.json` defines `generated_by_version` as the "version tag or commit of the implementation repository." `"design-notebook"` satisfies the type constraint (non-empty string) but provides no actionable version information for replay. You cannot check out `design-notebook` from any repository.

- `policy_id: "study-output-governance-v1.0.0"` — hardcoded policy reference that is never validated against the governance policy registry at runtime. The governance policy registry (`governance/policies/policy-registry.json`) contains policies with IDs in the pattern `GOV-001` through `GOV-010`. The policy `study-output-governance-v1.0.0` does not appear in that registry. This means the declared governing policy either does not exist in the registry or exists elsewhere with no registration — either way, the field is forensically meaningless.

**Why this is dangerous:**

Replay integrity depends on being able to reconstruct the exact conditions under which an artifact was produced. With static fields, a replay of an artifact from any run at any version looks identical. There is no way to detect version drift, source document changes, or policy evolution from the provenance record alone.

**How it fails in a real scenario:**

A regulatory audit requests replay of study run `run-abc123def456` to verify that it was produced under the currently active policy. The provenance record shows `policy_id: "study-output-governance-v1.0.0"`. An auditor cannot determine whether this policy was active, current, or even registered at the time of the run — because the field is a static literal that would appear identically in a run from two years ago and a run from today. The audit question cannot be answered. The system cannot certify its own compliance history.

---

### Finding 5 — Three provenance schemas are mutually incompatible with no cross-validation bridge

**Files:** `governance/schemas/provenance.schema.json`, `schemas/provenance-schema.json`, `contracts/schemas/provenance_record.schema.json`

**Finding:**

Three distinct JSON schemas each claim to govern provenance in this system. They are structurally incompatible:

**Schema A** (`governance/schemas/provenance.schema.json`) requires:
`run_id`, `artifact_id`, `policy_id`, `generated_by_engine`, `engine_version`, `source_artifacts`, `timestamp`, `repo`, `commit_sha`, `contract_version`

**Schema B** (`schemas/provenance-schema.json`) requires:
`record_id` (pattern `^PRV-[A-Z0-9._-]+$`), `record_type`, `source_document`, `source_revision`, `workflow_name`, `workflow_step`, `generated_by_system`, `generated_by_repo`, `generated_by_version`, `policy_id`, `schema_version` (const `"1.1.0"`), `created_at`, `updated_at`

**Schema C** (`contracts/schemas/provenance_record.schema.json`) requires:
`artifact_type`, `artifact_id`, `artifact_version`, `schema_version` (const `"1.0.0"`), `standards_version`, `record_id`, `run_id`, `created_at`, `created_by`, `source_repo`, `source_repo_version`, `record_type`, `entity_id`, `activity`, `agents`, `derived_from`, `lineage`

Incompatibilities are absolute, not incidental:

1. Schema B requires `schema_version = "1.1.0"` (const). Schema C requires `schema_version = "1.0.0"` (const). A document cannot satisfy both simultaneously.

2. Schema C requires `artifact_type = "provenance_record"` (const). Schema B's `additionalProperties: false` would reject an `artifact_type` field.

3. The `artifact_writer.py` provenance record satisfies Schema B's pattern partially (it has `record_id`, `policy_id`, `schema_version: "1.1.0"`) but is missing `commit_sha` required by Schema A, and is missing `agents`, `activity`, `lineage` required by Schema C.

No enforcement code validates a single provenance record against all three schemas before artifact acceptance. No gating mechanism ensures a record's schema compliance. The runtime validation checks are per-artifact-type, not cross-schema.

**Why this is dangerous:**

A record that "passes validation" may have done so against the least restrictive schema. The most demanding schema (Schema C) requires forensic fields — `agents`, `activity`, `lineage`, `standards_version` — that are entirely absent from records emitted by `artifact_writer.py`. Any downstream system that relies on Schema C for audit-grade provenance will encounter artifacts that pass Schema B validation but fail Schema C validation, with no error raised during production.

**How it fails in a real scenario:**

An audit pipeline imports all provenance records and validates them against `contracts/schemas/provenance_record.schema.json` (Schema C) because that is the contract-layer schema, the most authoritative for cross-system exchange. All records produced by `artifact_writer.py` fail validation — missing `agents`, `activity`, `lineage`, `standards_version`. The audit pipeline cannot process these artifacts. The audit fails, not because the artifacts are fraudulent, but because they were validated against the wrong schema during production.

---

## Required Fixes

### Fix 1 — Wire trace context into `artifact_writer.py`

**Location:** `spectrum_systems/study_runner/artifact_writer.py:36–51, 167–204`

`write_outputs()` must accept a `trace_id` and `span_id` parameter. These values must be passed to `_provenance_record()` and included in the returned dict as required fields.

```python
# _provenance_record must emit:
{
    ...
    "trace_id": trace_id,          # required, must be non-empty UUID
    "span_id": span_id,            # required, must be non-empty UUID
    ...
}
```

`write_outputs()` must raise `ValueError` if `trace_id` or `span_id` is absent or empty — not emit with None or omit. The trace engine's `validate_trace_context(trace_id, span_id)` must be called before any artifact is written; any errors returned must abort the write with an exception.

### Fix 2 — Add `policy_id` to `create_artifact_metadata()` as a required parameter

**Location:** `shared/adapters/artifact_emitter.py:72–107`

`policy_id` must be added as a required keyword argument with no default value. The function must validate `policy_id` against the pattern `^[a-z][a-z0-9-]*-v\d+\.\d+\.\d+$` using `re.fullmatch`. If the pattern fails, raise `ValueError`.

```python
def create_artifact_metadata(
    *,
    artifact_id: str,
    artifact_type: str,
    module_origin: str,
    lifecycle_state: str,
    contract_version: str,
    policy_id: str,                    # ADD — required, no default
    schema_version: str = "1.0.0",
    run_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    ...
    _require_policy_id(policy_id)      # ADD — pattern validation
    ...
    record["policy_id"] = policy_id    # ADD — included in output
```

All existing callers must be updated to supply `policy_id`.

### Fix 3 — Replace `build_provenance()` in strategic knowledge with a schema-validated builder

**Location:** `spectrum_systems/modules/strategic_knowledge/provenance.py:13–20`

The existing `build_provenance()` function must be replaced with one that produces a record conforming to `schemas/provenance-schema.json`. At minimum:

```python
def build_provenance(
    *,
    extraction_run_id: str,
    extractor_version: str,
    policy_id: str,
    workflow_name: str,
    workflow_step: str,
    generated_by_repo: str,
    source_document: str,
    source_revision: str,
    trace_id: str,
    notes: str | None = None,
) -> dict:
```

The function must:
1. Validate `policy_id` against `^[a-z][a-z0-9-]*-v\d+\.\d+\.\d+$`
2. Validate `source_revision` against `^rev[0-9]+$`
3. Generate a `record_id` matching `^PRV-[A-Z0-9._-]+$`
4. Set `schema_version = "1.1.0"` (const)
5. Validate the complete output dict against `schemas/provenance-schema.json` before returning — raise if validation fails

### Fix 4 — Replace static fields in `_provenance_record()` with runtime-derived values

**Location:** `spectrum_systems/study_runner/artifact_writer.py:41, 46, 47`

- `source_revision` must be passed in as a parameter from the calling context, not hardcoded as `"rev0"`.
- `generated_by_version` must be derived from the actual commit SHA of the repository at runtime (e.g., `git rev-parse --short HEAD` captured at process start) or injected via environment variable — never a static label.
- `policy_id` must be validated at runtime against the governance policy registry. If the registry does not contain an active policy matching the provided `policy_id`, the write must be aborted with an exception.

`write_outputs()` signature must be extended:

```python
def write_outputs(
    config: StudyConfig,
    pipeline_outputs: dict,
    logger,
    source_revision: str,      # ADD
    generated_by_version: str, # ADD — must be semver or commit sha
    policy_id: str,            # ADD — validated against registry
    trace_id: str,             # ADD — from Finding 1
    span_id: str,              # ADD — from Finding 1
) -> Dict[str, str]:
```

### Fix 5 — Designate a single authoritative provenance schema and enforce it at all emission points

**Scope:** `governance/schemas/provenance.schema.json`, `schemas/provenance-schema.json`, `contracts/schemas/provenance_record.schema.json`

One schema must be declared authoritative for all runtime artifact emission. The other schemas must either be deprecated (removed from active use) or explicitly scoped to a non-overlapping domain with enforcement gates ensuring no artifact crosses schema domains.

The authoritative schema must be the superset. The current candidate is `contracts/schemas/provenance_record.schema.json` (Schema C) because it is the most complete. All emission functions — `_provenance_record()`, `build_provenance()`, `create_artifact_metadata()` — must validate their output against this single authoritative schema before returning.

Any schema that cannot validate a record that a different schema accepts must be resolved. The `schema_version` const conflict (`"1.1.0"` vs `"1.0.0"`) must be resolved to a single value.

---

## Optional Improvements

### OI-1 — Fail hard on `"unknown-trace"` and `"unknown-decision"` in legacy enforcement path

**Location:** `spectrum_systems/modules/runtime/enforcement_engine.py:150–152`

The `enforce_budget_decision()` function currently falls back to `"unknown-trace"` and `"unknown-decision"` when `trace_id` or `decision_id` is absent:

```python
default_decision_id = str((decision or {}).get("decision_id") or "unknown-decision")
default_trace_id = str((decision or {}).get("trace_id") or "unknown-trace")
```

These are fail-open fallbacks in a declared fail-closed system. While `enforce_budget_decision()` is deprecated, it remains an active code path for existing replay flows. An artifact produced with `trace_id: "unknown-trace"` is forensically indistinguishable from an artifact produced under genuine conditions with a lost trace. Replace both fallbacks with `EnforcementError` raises.

### OI-2 — Attach provenance to KML map artifacts

**Location:** `spectrum_systems/study_runner/artifact_writer.py:98–114`

`write_maps()` writes KML artifacts with no provenance field. All other artifact types emitted by `artifact_writer.py` include a provenance block. The KML artifacts should receive the same provenance treatment. Currently these artifacts are forensic orphans.

---

## Trust Assessment

| Capability | Status | Justification |
|------------|--------|---------------|
| **Audit** | NO | Artifacts from `artifact_writer.py` have no trace linkage, static version fields, and a policy reference that cannot be validated against the registry. Schema fragmentation means an auditor cannot know which schema applies. |
| **Replay** | NO | `source_revision: "rev0"` and `generated_by_version: "design-notebook"` are static literals. A replay cannot reconstruct the source document revision or software version. No trace_id means the execution context cannot be recovered. |
| **Enforcement traceability** | NO | Strategic knowledge artifacts use a schema-free shadow provenance model with no policy_id, trace_id, or schema version. These artifacts exist entirely outside the enforcement governance layer. |

---

## Failure Mode Summary

**Worst realistic failure:**

A strategic knowledge extraction run is performed using `build_provenance()` from `spectrum_systems/modules/strategic_knowledge/provenance.py`. The resulting artifacts carry provenance consisting only of `extraction_run_id` and `extractor_version` — no `policy_id`, no `trace_id`, no `schema_version`, no `record_id`. These artifacts are then persisted via `create_artifact_metadata()` from the shared emitter, which also omits `policy_id`. Both functions bypass all provenance schema validation.

The artifacts enter the governance pipeline. Because they claim `schema_version: "1.0.0"` (the emitter default), they are validated against the least restrictive schema context. No validation failure is raised. The artifacts advance through lifecycle states — `input` → `transformed` → `evaluated` — and are eventually marked `resolved`.

Six months later, a regulatory inquiry demands reconstruction of the decision provenance for these artifacts. The artifacts have:
- No `policy_id` — the governing policy is unknown
- No `trace_id` — the execution context cannot be recovered
- No `commit_sha` / `generated_by_version` — the exact software version is unknown
- `source_revision: "rev0"` or equivalent static literal — the source document version is unverifiable

The system cannot answer the inquiry. The artifacts are forensically opaque. Because no failure was raised during production, there is no error log to consult. The system's own records show the artifacts as fully `resolved` with valid provenance — because the provenance was never validated against the schemas that would have caught these gaps. The inquiry cannot be closed with confidence.

This failure is silent, complete, and irreversible.
