# Runtime System Design

## Purpose

This document describes the runtime compatibility enforcement layer
(Prompt BC) for Spectrum Systems.  This layer validates every execution
bundle *before* a job is allowed to run, ensuring that the system only
executes bundles that are fully compatible with the active runtime
environment.

---

## Runtime Validation Lifecycle

```
Bundle submitted for execution
          │
          ▼
┌────────────────────────────┐
│  1. Manifest Integrity     │  Missing required fields → reject_execution
│     validate_manifest_     │
│     integrity()            │
└────────────┬───────────────┘
             │ (only if manifest intact)
             ▼
┌────────────────────────────┐
│  2. MATLAB Runtime Version │  Mismatch → reject_execution
│     validate_matlab_       │
│     runtime_version()      │
└────────────┬───────────────┘
             ▼
┌────────────────────────────┐
│  3. Platform Compatibility │  OS mismatch → reject_execution
│     validate_platform_     │
│     compatibility()        │
└────────────┬───────────────┘
             ▼
┌────────────────────────────┐
│  4. Required Artifacts     │  Missing files → require_rebuild
│     validate_required_     │
│     artifacts()            │
└────────────┬───────────────┘
             ▼
┌────────────────────────────┐
│  5. Entrypoint Validation  │  Absent/non-executable → reject_execution
│     validate_entrypoint()  │
└────────────┬───────────────┘
             ▼
┌────────────────────────────┐
│  6. Cache Policy           │  Cache required but unavailable →
│     validate_cache_        │  require_environment_update
│     policy()               │
└────────────┬───────────────┘
             ▼
┌────────────────────────────┐
│  7. derive_runtime_        │  Aggregates all conditions into a
│     decision()             │  deterministic system response
└────────────┬───────────────┘
             ▼
     Decision artifact
     persisted to
     data/runtime_decisions/
             │
    compatible? ──── Yes ──▶ allow_execution
             │
            No
             ▼
     Execution blocked
```

---

## Failure Types and System Responses

| failure_type | system_response | When triggered |
|---|---|---|
| `manifest_invalid` | `reject_execution` | Required fields missing from bundle manifest |
| `runtime_version_mismatch` | `reject_execution` | Installed MATLAB Runtime ≠ required version |
| `platform_mismatch` | `reject_execution` | Running OS ≠ bundle's required_platform |
| `invalid_entrypoint` | `reject_execution` | entrypoint_script absent or not executable |
| `missing_artifacts` | `require_rebuild` | One or more required_files not found on disk |
| `cache_unavailable` | `require_environment_update` | Cache policy required but cache not available |

---

## Why Strict Rejection Is Required

The MATLAB Runtime report and the BB+1 enforcement layer both identify
execution-environment inconsistency as a leading source of silent
failures.  Specifically:

- **Version drift** — Running a bundle compiled against R2024b on an R2023a
  runtime produces undefined behavior or silent wrong results.
- **Platform drift** — Linux-compiled binaries do not run on Windows and
  vice versa; a soft-fail here would produce cryptic errors deep in the
  pipeline.
- **Missing artifacts** — Partial artifact availability means partial
  results that are silently incorrect rather than explicitly absent.
- **Entrypoint issues** — A non-executable entrypoint fails at OS level,
  producing an error that is hard to trace back to bundle validity.
- **Cache instability** — Bundles that declare a required cache policy must
  fail early if the cache is absent rather than producing inconsistent
  timing or correctness.

**No soft validation.  No fallback versions.  Fail fast, fail hard.**

Every decision is persisted as a JSON artifact so that failures are
auditable and traceable.

---

## Relationship to BB+1 Enforcement Layer

The BB+1 failure enforcement layer (Prompt BB) governs *output quality*
decisions: whether to allow promotion, suppress a component, or flag an
incident based on observability metrics.

The runtime compatibility enforcement layer (Prompt BC) governs
*execution environment* decisions: whether to allow a bundle to start
execution at all.

```
┌─────────────────────────────────────────────────────────┐
│                   Execution pipeline                     │
│                                                          │
│  Bundle submitted                                        │
│        │                                                 │
│        ▼                                                 │
│  ┌─────────────────────────────┐                         │
│  │  BC: Runtime Compatibility  │ ◀── This layer          │
│  │  Enforcement                │    blocks invalid       │
│  │  (pre-execution gate)       │    environments         │
│  └──────────────┬──────────────┘                         │
│                 │ allow_execution                         │
│                 ▼                                         │
│         Job runs                                          │
│                 │                                         │
│                 ▼                                         │
│  ┌─────────────────────────────┐                         │
│  │  BB: Failure-First          │ ◀── Output quality      │
│  │  Observability + BB+1       │    gate; blocks         │
│  │  Enforcement                │    bad promotions       │
│  └─────────────────────────────┘                         │
└─────────────────────────────────────────────────────────┘
```

BC fires *before* BB.  If BC rejects a bundle, BB never sees it.

---

## Artifacts

### Decision artifact

Every call to `validate_runtime_environment()` produces a decision
artifact conforming to:

```
contracts/schemas/runtime_compatibility_decision.schema.json
```

Decisions are persisted to:

```
data/runtime_decisions/runtime_compatibility_decision_<timestamp>.json
```

The latest decision is also written to:

```
outputs/runtime_validation_decision.json
```

### Key fields

| Field | Description |
|---|---|
| `decision_id` | Unique identifier derived from bundle_id + created_at |
| `bundle_id` | ID of the bundle being validated |
| `compatible` | True only when all validators pass |
| `system_response` | One of: allow_execution, reject_execution, require_rebuild, require_environment_update |
| `failure_type` | Most severe failure type, or null when compatible |
| `triggering_conditions` | Full list of validation error strings |
| `runtime_env_snapshot` | Captured OS, MATLAB version, Python version, disk space, hostname |

---

## CLI

```bash
python scripts/run_runtime_validation.py <bundle_manifest.json> \
    [--runtime-env <json_string_or_path>] \
    [--base-path <directory>]
```

Exit codes:
- `0` — Compatible, execution allowed
- `1` — Incompatible, execution blocked
- `2` — Unexpected error (bad input, schema violation)

---

## Module location

```
spectrum_systems/modules/runtime/runtime_compatibility.py
```

Core functions:

| Function | Purpose |
|---|---|
| `validate_runtime_environment()` | Top-level entry point; runs all validators |
| `validate_matlab_runtime_version()` | Checks MATLAB Runtime version exact match |
| `validate_platform_compatibility()` | Checks OS/platform match |
| `validate_required_artifacts()` | Checks required_files exist on disk |
| `validate_entrypoint()` | Checks entrypoint_script exists and is executable |
| `validate_cache_policy()` | Checks cache availability if required |
| `validate_manifest_integrity()` | Checks all required fields are present |
| `derive_runtime_decision()` | Aggregates conditions into a system response |
| `classify_runtime_failure()` | Returns the most severe failure type |
| `capture_runtime_env_snapshot()` | Captures the current execution environment |
