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

---

## BD — Run Bundle Contract + Manifest Hardening

### Purpose

The BD layer governs what a run bundle **must contain** and **promises to produce**
before BC runtime compatibility validation is attempted.  BC validates the
environment; BD validates the bundle itself.

```
Bundle submitted for execution
          │
          ▼
┌────────────────────────────────────────────────────┐
│  BD: Run Bundle Contract + Manifest Hardening      │
│  (bundle correctness gate)                         │
│  scripts/run_bundle_validation.py                  │
└──────────────────────────┬─────────────────────────┘
                           │ valid bundle contract
                           ▼
┌────────────────────────────────────────────────────┐
│  BC: Runtime Compatibility Enforcement             │
│  (environment gate)                                │
│  scripts/run_runtime_validation.py                 │
└──────────────────────────┬─────────────────────────┘
                           │ allow_execution
                           ▼
                      Job runs
```

BD fires **before** BC.  A bundle with an invalid manifest or missing
output contract never reaches runtime validation.

---

### Required Bundle Layout

A valid run bundle must contain a manifest JSON file
(`run_bundle_manifest.json`) conforming to:

```
contracts/schemas/run_bundle_manifest.schema.json
```

Example on-disk layout:

```
bundle-root/
├── run_bundle_manifest.json      ← governed manifest (this schema)
├── bin/
│   └── run_spectral_analysis.sh  ← worker_entrypoint
├── inputs/
│   ├── spectrum_cases.json       ← required input
│   └── parameters.mat            ← required input
├── outputs/
│   ├── results_summary.json      ← results_summary_json (paper_relevant)
│   ├── provenance.json           ← provenance_json
│   └── raw/
│       └── results.mat           ← raw_mat
├── figures/                      ← figure_dir (paper_relevant)
├── tables/                       ← table_dir (paper_relevant)
└── logs/
    └── worker.log                ← log_file
```

---

### Manifest Field Definitions

| Field | Type | Description |
|---|---|---|
| `bundle_version` | string (semver) | Schema/format version of this manifest |
| `run_id` | string | Unique identifier for this run bundle |
| `matlab_release` | string | MATLAB release string, e.g. `R2024b` |
| `runtime_version_required` | string | Exact MCR version required |
| `platform` | enum | `windows-x86_64` or `linux-x86_64` |
| `worker_entrypoint` | string | Relative path to the executable/script |
| `component_cache.mcr_cache_root` | string | Path to MCR cache root |
| `component_cache.mcr_cache_size` | string | Max cache size, e.g. `2GB` |
| `startup_options.logfile` | string | Relative path to worker log |
| `startup_options.environment_vars` | object | Key/value env vars |
| `startup_options.timeout_seconds` | integer | Max execution time |
| `inputs` | array | Explicit list of all input artifacts |
| `inputs[].path` | string | Relative path to input file |
| `inputs[].type` | string | Input artifact type |
| `inputs[].required` | boolean | Whether the input is mandatory |
| `inputs[].content_hash` | string | Optional SHA-256 for integrity |
| `expected_outputs` | array | Explicit list of expected outputs |
| `expected_outputs[].path` | string | Relative path of expected output |
| `expected_outputs[].type` | enum | See output types below |
| `expected_outputs[].required` | boolean | Whether output is mandatory |
| `expected_outputs[].paper_relevant` | boolean | Whether output feeds a working paper |
| `provenance` | object | Replay and traceability fields |
| `execution_policy` | object | Retry and idempotency declaration |
| `created_at` | string (date-time) | ISO 8601 creation timestamp |

#### Output types

| Type | Description |
|---|---|
| `results_summary_json` | Summary of computed results |
| `provenance_json` | Provenance record for the run |
| `raw_mat` | Raw MATLAB results file |
| `figure_dir` | Directory of generated figures |
| `table_dir` | Directory of generated tables |
| `log_file` | Worker execution log |

---

### Output Contract Rules

A valid bundle **must** declare at least:

1. One `results_summary_json` output
2. One `provenance_json` output
3. One `log_file` output
4. At least one output with `paper_relevant: true`

Failure to satisfy any of these rules produces `output_contract_invalid`.

---

### Provenance Minimums

The `provenance` block must declare:

| Field | Requirement |
|---|---|
| `source_case_ids` | Non-empty list of case IDs |
| `manifest_author` | Non-empty string |
| `creation_context` | Non-empty string |
| `rng_seed` or `rng_state_ref` | At least one must be declared |

Failure produces `provenance_incomplete`.

---

### Idempotency Policy

`execution_policy.idempotency_mode` must be declared explicitly as one of:

| Value | Meaning |
|---|---|
| `safe_rerun` | Re-running this bundle produces the same outputs |
| `strict_once` | Bundle must run exactly once; re-run is forbidden |

An absent or empty `idempotency_mode` produces `idempotency_undefined`.

---

### Relationship to BC Runtime Validation

| Layer | Validates | Failure blocks |
|---|---|---|
| **BD** | Bundle manifest correctness, output contract, provenance, idempotency | BC validation attempt |
| **BC** | Runtime environment compatibility | Job execution |

The two layers are intentionally separate:
- **BD = bundle correctness** — does the bundle declare everything it needs?
- **BC = environment compatibility** — does the runtime satisfy what the bundle requires?

---

### Example Manifest

```json
{
  "bundle_version": "1.0.0",
  "run_id": "run-matlab-spectral-analysis-2024b-001",
  "matlab_release": "R2024b",
  "runtime_version_required": "R2024b",
  "platform": "linux-x86_64",
  "worker_entrypoint": "bin/run_spectral_analysis.sh",
  "component_cache": {
    "mcr_cache_root": "/tmp/mcr_cache",
    "mcr_cache_size": "2GB"
  },
  "startup_options": {
    "logfile": "logs/worker.log",
    "environment_vars": { "MCR_CACHE_ROOT": "/tmp/mcr_cache" },
    "timeout_seconds": 3600
  },
  "inputs": [
    { "path": "inputs/spectrum_cases.json", "type": "case_definition", "required": true, "content_hash": "sha256:abc123" },
    { "path": "inputs/parameters.mat", "type": "matlab_parameters", "required": true },
    { "path": "inputs/optional_seed_override.json", "type": "rng_seed_override", "required": false }
  ],
  "expected_outputs": [
    { "path": "outputs/results_summary.json", "type": "results_summary_json", "required": true, "paper_relevant": true },
    { "path": "outputs/provenance.json", "type": "provenance_json", "required": true, "paper_relevant": false },
    { "path": "outputs/raw/results.mat", "type": "raw_mat", "required": true, "paper_relevant": false },
    { "path": "outputs/figures/", "type": "figure_dir", "required": false, "paper_relevant": true },
    { "path": "outputs/tables/", "type": "table_dir", "required": false, "paper_relevant": true },
    { "path": "logs/worker.log", "type": "log_file", "required": true, "paper_relevant": false }
  ],
  "provenance": {
    "source_artifact_ids": ["artifact-spectrum-v3-2024b"],
    "source_case_ids": ["case-001", "case-002", "case-003"],
    "rng_seed": 42,
    "manifest_author": "spectrum-pipeline-agent",
    "creation_context": "Automated spectral analysis run for Q4-2024 working paper draft."
  },
  "execution_policy": {
    "idempotency_mode": "safe_rerun",
    "retry_allowed": true,
    "max_retries": 2,
    "stale_claim_timeout_hours": 4.0
  },
  "created_at": "2024-11-15T12:00:00Z"
}
```

---

### Artifacts

Every call to `validate_bundle_contract()` produces a decision artifact
conforming to:

```
contracts/schemas/run_bundle_validation_decision.schema.json
```

Decisions are persisted to:

```
data/run_bundle_decisions/run_bundle_validation_decision_<timestamp>.json
```

The latest decision is also written to:

```
outputs/run_bundle_validation_decision.json
```

### Key BD decision fields

| Field | Description |
|---|---|
| `decision_id` | Unique ID derived from run_id + created_at |
| `run_id` | ID of the bundle being validated |
| `valid` | True only when all hardening rules pass |
| `failure_type` | Most severe failure type, or null when valid |
| `triggering_conditions` | Full list of validation error strings |
| `bundle_summary` | Concise summary of key bundle fields |

### BD failure types

| failure_type | When triggered |
|---|---|
| `manifest_invalid` | Required fields missing or schema violation |
| `missing_required_input` | A required input has no path or is absent on disk |
| `output_contract_invalid` | Missing required output types or no paper_relevant output |
| `provenance_incomplete` | Missing source_case_ids, author, context, or RNG |
| `idempotency_undefined` | idempotency_mode absent or empty |

---

### CLI

```bash
python scripts/run_bundle_validation.py <bundle_manifest.json|bundle_root_dir> \
    [--bundle-root <directory>]
```

Exit codes:
- `0` — Valid — bundle contract satisfied
- `1` — Invalid manifest or contract violation
- `2` — Runtime/path-related error (bad input, schema load failure)

---

### Module location

```
spectrum_systems/modules/runtime/run_bundle.py
```

Core functions:

| Function | Purpose |
|---|---|
| `load_run_bundle_manifest()` | Load and parse a manifest JSON file |
| `normalize_run_bundle_manifest()` | Stable-format normalization (no error hiding) |
| `validate_run_bundle_manifest()` | JSON Schema structural validation |
| `validate_bundle_contract()` | Top-level BD entry point; runs all hardening rules |
| `validate_expected_outputs()` | Checks output-type and paper_relevant requirements |
| `validate_input_paths()` | Checks required inputs declared and optionally on disk |
| `validate_output_contract()` | Alias for validate_expected_outputs |
| `validate_provenance_fields()` | Checks provenance replay minimums |
| `derive_bundle_summary()` | Returns concise summary dict for auditing |
| `classify_bundle_failure()` | Returns most severe failure type |

---

## BE — Run Output Normalization + Evaluation

### Purpose

BE answers the question: **"What did this run mean, is it complete, and should we trust it enough to compare or use downstream?"**

BC validates runtime compatibility. BD validates bundle contract and manifest discipline. BE sits after BD and before any downstream integration. It converts a BD-valid run bundle into a normalized, comparable, evaluation-ready result artifact.

BE is **runtime-agnostic**. MATLAB is treated as a future producer only. No MATLAB-specific logic exists in BE. The module defends itself against malformed or missing output files even when BD has already passed.

### Relationship: BC → BD → BE

```
BC: Is the environment capable of running this job?
BD: Does the bundle manifest conform to the governed contract?
BE: What did the run produce, is it complete, and can we trust it?
```

BC and BD validate before execution. BE validates after execution, transforming raw outputs into governed artifacts.

### Module location

```
spectrum_systems/modules/runtime/run_output_evaluation.py
```

### Core functions

| Function | Purpose |
|---|---|
| `load_json_file(path)` | Load and parse a JSON file safely |
| `resolve_manifest_output_paths(manifest, bundle_root)` | Resolve declared output paths to absolute paths |
| `extract_results_summary(outputs)` | Extract results_summary from resolved outputs |
| `extract_provenance(outputs)` | Extract provenance from resolved outputs |
| `infer_study_type(manifest, results_summary)` | Infer study_type from manifest or results_summary |
| `get_required_metrics_for_study_type(study_type)` | Return required metric catalog for a study type |
| `normalize_summary_metrics(study_type, results_summary)` | Normalize metrics to governed array shape |
| `compute_completeness(required, normalized)` | Compute completeness status |
| `build_threshold_assessments(study_type, metrics, manifest, rs)` | Evaluate declared thresholds |
| `detect_outlier_flags(metrics)` | Flag NaN, infinite, and extreme-magnitude values |
| `compute_readiness(completeness, thresholds, findings)` | Determine readiness signal |
| `build_normalized_run_result(manifest, rs, prov, bundle_root)` | Build the NRR artifact |
| `classify_evaluation_failure(findings)` | Classify overall status and failure_type |
| `build_run_output_evaluation_decision(source_bundle_id, findings)` | Build the ROE decision artifact |
| `validate_normalized_run_result(payload)` | Validate NRR against schema |
| `validate_run_output_evaluation_decision(payload)` | Validate ROE against schema |
| `evaluate_run_outputs(manifest_path, bundle_root, manifest_payload)` | Top-level BE entry point |

### Normalized artifact structure

BE emits two governed artifacts:

**1. normalized_run_result** (`NRR-*`)
Contains:
- `artifact_id`, `artifact_type`, `schema_version`
- `source_bundle_id` — links back to the BD-validated run_id
- `study_type` — inferred from manifest or results_summary
- `scenario` — scenario_id, label, frequency range, assumptions
- `metrics` — metric_set_id, summary_metrics array, completeness
- `evaluation_signals` — readiness, outlier_flags, threshold_assessments, trust_notes
- `provenance` — manifest_author, source_case_ids, rng_reference, source paths
- `generated_at`

**2. run_output_evaluation_decision** (`ROE-*`)
Contains:
- `decision_id`, `artifact_type`, `schema_version`
- `source_bundle_id`
- `overall_status` — pass / warning / fail
- `failure_type` — most severe failure type
- `findings` — structured list of all findings with code, severity, message, artifact_path
- `generated_at`

### Study-type required metrics

| study_type | Required metrics |
|---|---|
| `p2p_interference` | interference_power_dbm, in_ratio_db, path_loss_db |
| `adjacency_analysis` | frequency_separation_mhz, interference_power_dbm |
| `retuning_analysis` | incumbent_links_impacted, retune_candidate_count |
| `sharing_study` | interference_power_dbm, affected_receivers_count |
| `generic` | (none) |

### Readiness semantics

| readiness | Conditions |
|---|---|
| `ready_for_comparison` | Completeness complete, no errors, no threshold failures |
| `limited_use` | Completeness partial, or threshold failure, or outlier flags present |
| `not_ready` | Completeness insufficient, or any error-level finding |

### Threshold handling

BE looks for threshold definitions in:
- `manifest["evaluation_thresholds"]`
- `results_summary["evaluation_thresholds"]`

Each threshold may define: `metric_name`, `threshold_name`, `operator` (lt/lte/gt/gte/eq), `value`.

If a threshold is malformed, the assessment status is `unknown` and a finding is emitted.
If the referenced metric is absent, the assessment status is `unknown`.

### Artifacts

Every call to `evaluate_run_outputs()` produces:

```
outputs/normalized_run_result.json
outputs/run_output_evaluation_decision.json
```

Archived under:

```
data/run_output_evaluation_decisions/run_output_evaluation_decision_<timestamp>.json
```

### CLI

```bash
python scripts/run_output_evaluation.py --manifest path/to/run_bundle_manifest.json
python scripts/run_output_evaluation.py --bundle-root path/to/bundle_dir
```

Exit codes:
- `0` — pass
- `1` — warning
- `2` — fail

---

## BF — Cross-Run Intelligence and Anomaly Detection

### Purpose

BF answers the decision-support question that BC, BD, and BE cannot:

> *How does this run compare to other runs, what is abnormal, and what
> should decision-makers pay attention to?*

The layer consumes multiple BE-produced `normalized_run_result` artifacts,
aligns their metrics, ranks scenarios, detects anomalies, and emits two
governed artifacts — a `cross_run_comparison` and a
`cross_run_intelligence_decision` — that feed directly into working paper
reviews, study gate checks, and operator triage.

### Relationship: BC → BD → BE → BF

```
BC validates the runtime environment
 └─▶ BD validates the bundle contract
      └─▶ BE normalizes run outputs into NRR artifacts
           └─▶ BF compares NRR artifacts across runs
                ├─▶ cross_run_comparison.json
                └─▶ cross_run_intelligence_decision.json
```

BF does not re-execute runs, re-validate bundle contracts, or perform
any MATLAB-specific logic. It is runtime-agnostic: it consumes NRR
artifacts regardless of how they were produced.

### Metric alignment logic

Metrics are aligned by `metric_name`. For each metric present across
any of the inputs, BF builds a `metric_comparison` record.

Comparability rules:

| comparability_status | When set |
|---|---|
| `comparable` | All values share the same unit AND ≥ 2 numeric values exist |
| `mixed_units` | Same metric_name appears with different units across runs |
| `insufficient_data` | Fewer than 2 usable numeric values exist |
| `inconsistent_structure` | Values present but non-numeric where numeric expected |

Summary statistics (count, min, max, range, mean) are computed only when
`comparability_status == comparable`.

### Study type comparison rules

BF enforces that all compared runs share the same study type.

| Scenario | Result |
|---|---|
| All runs have the same non-generic study_type | Accepted; rankings apply |
| All runs have study_type `generic` | Accepted; no default rankings |
| One non-generic type + some `generic` runs | Accepted with warning; generic runs included but may lack required metrics |
| Multiple distinct non-generic study types | **Rejected** with `failure_type=mixed_study_types` |

### Ranking behavior

Rankings are computed per study type using a fixed set of ranking bases.
Rankings are only produced when:
- The metric is `comparable`
- At least 2 numeric values exist for that metric

Default ranking bases:

| study_type | metric_name | direction |
|---|---|---|
| `p2p_interference` | interference_power_dbm | descending |
| `p2p_interference` | in_ratio_db | descending |
| `adjacency_analysis` | interference_power_dbm | descending |
| `retuning_analysis` | incumbent_links_impacted | descending |
| `retuning_analysis` | retune_candidate_count | descending |
| `sharing_study` | interference_power_dbm | descending |
| `sharing_study` | affected_receivers_count | descending |
| `generic` | (none) | — |

### Anomaly detection philosophy

BF implements lightweight, conservative anomaly detection only. Every
check is designed to be:

- **Deterministic** — same inputs always produce the same flags
- **Safe-fail** — flags are warnings or errors, never silent drops
- **Traceable** — every flag includes `affected_runs` and `metric_name`
- **Explainable** — detail strings are human-readable

Implemented anomaly types:

| flag_type | severity | trigger |
|---|---|---|
| `extreme_spread` | error | `abs(mean) > 0 AND range > 10 * abs(mean)` |
| `duplicate_scenario_id` | warning | Same scenario_id in multiple runs with materially different metric values |
| `readiness_mismatch` | warning | Run is `ready_for_comparison` but completeness is not `complete` |
| `mixed_units` | warning | Same metric appears with multiple units |
| `low_sample_count` | warning | Only 2 values exist AND range > abs(mean) |

### Why BF remains runtime-agnostic

BF operates exclusively on NRR artifacts. It has no knowledge of:
- MATLAB versions, platforms, or entrypoints (BC concerns)
- Bundle contract validation (BD concerns)
- How metrics were computed or what simulation was run

This means BF can compare outputs from any normalized execution: MATLAB,
Python, or any future runtime — as long as BE has normalized them.

### Operator workflow examples

**Compare two p2p_interference runs:**

```bash
python scripts/cross_run_intelligence.py \
    --input run_a/outputs/normalized_run_result.json \
    --input run_b/outputs/normalized_run_result.json \
    --output-dir outputs/comparison/
```

**Auto-discover NRR files in a study directory:**

```bash
python scripts/cross_run_intelligence.py \
    --dir studies/p2p_batch/ \
    --output-dir outputs/batch_comparison/
```

Exit codes:
- `0` — pass (no warnings or errors)
- `1` — warning (comparison succeeded, anomalies detected)
- `2` — fail (missing inputs, schema errors, mixed study types)

### Artifacts

Every call to `compare_normalized_runs()` produces:

```
cross_run_comparison.json
cross_run_intelligence_decision.json
```

Archived under:

```
data/cross_run_intelligence_decisions/cross_run_intelligence_decision_<timestamp>.json
```

### Example: cross_run_comparison

```json
{
  "artifact_id": "CRC-A1B2C3D4E5F6",
  "artifact_type": "cross_run_comparison",
  "schema_version": "1.0.0",
  "comparison_id": "CMP-123456789ABC",
  "study_type": "p2p_interference",
  "compared_runs": [
    {
      "source_bundle_id": "bundle-p2p-001",
      "normalized_run_result_id": "NRR-P2P-RUN1-001",
      "scenario_id": "scenario-alpha",
      "scenario_label": "P2P Alpha Link",
      "readiness": "ready_for_comparison",
      "completeness_status": "complete"
    },
    {
      "source_bundle_id": "bundle-p2p-002",
      "normalized_run_result_id": "NRR-P2P-RUN2-001",
      "scenario_id": "scenario-beta",
      "scenario_label": "P2P Beta Link",
      "readiness": "ready_for_comparison",
      "completeness_status": "complete"
    }
  ],
  "metric_comparisons": [
    {
      "metric_name": "interference_power_dbm",
      "unit": "dBm",
      "compared_values": [
        {
          "source_bundle_id": "bundle-p2p-001",
          "scenario_id": "scenario-alpha",
          "value": -85.3,
          "classification": "core",
          "source_path": "outputs/results_summary.json#metrics[0]"
        },
        {
          "source_bundle_id": "bundle-p2p-002",
          "scenario_id": "scenario-beta",
          "value": -92.1,
          "classification": "core",
          "source_path": "outputs/results_summary.json#metrics[0]"
        }
      ],
      "summary_statistics": {
        "count": 2,
        "min": -92.1,
        "max": -85.3,
        "range": 6.8,
        "mean": -88.7
      },
      "comparability_status": "comparable"
    }
  ],
  "scenario_rankings": [
    {
      "ranking_basis": "interference_power_dbm",
      "direction": "descending",
      "ranked_scenarios": [
        {
          "rank": 1,
          "source_bundle_id": "bundle-p2p-001",
          "scenario_id": "scenario-alpha",
          "scenario_label": "P2P Alpha Link",
          "metric_name": "interference_power_dbm",
          "value": -85.3
        },
        {
          "rank": 2,
          "source_bundle_id": "bundle-p2p-002",
          "scenario_id": "scenario-beta",
          "scenario_label": "P2P Beta Link",
          "metric_name": "interference_power_dbm",
          "value": -92.1
        }
      ]
    }
  ],
  "anomaly_flags": [],
  "generated_at": "2026-03-19T10:00:00+00:00"
}
```

### Example: cross_run_intelligence_decision

```json
{
  "artifact_type": "cross_run_intelligence_decision",
  "schema_version": "1.0.0",
  "decision_id": "CRI-F1E2D3C4B5A6",
  "comparison_id": "CMP-123456789ABC",
  "overall_status": "pass",
  "failure_type": "none",
  "findings": [],
  "generated_at": "2026-03-19T10:00:00+00:00"
}
```

---

## BG — Working Paper Evidence Pack Synthesis

### Purpose

BG converts the technical outputs of BE and BF into a governed evidence
pack that is ready for downstream working-paper drafting, agency review,
and policy follow-up. It does **not** generate polished final prose. Its
job is to assemble trustworthy, traceable, decision-relevant evidence
blocks so that any later drafting is grounded, auditable, and defensible.

### Relationship: BC → BD → BE → BF → BG

```
BC  validates runtime environment (can this run execute here?)
BD  validates bundle contract (is this bundle contractually valid?)
BE  normalizes run outputs (what did this run mean; is it usable?)
BF  compares runs (how do runs compare; what stands out across them?)
BG  synthesizes evidence (what evidence should go into the paper,
    what findings matter most, what caveats must be carried forward,
    and what questions should be posed back to agencies or reviewers?)
```

BG consumes one or more BE `normalized_run_result` artifacts and,
optionally, one BF `cross_run_comparison` artifact. It produces two
governed output artifacts:

- `working_paper_evidence_pack` — section-organised evidence blocks
- `working_paper_synthesis_decision` — synthesis outcome and findings

### Why Evidence Packs Instead of Final Prose

Final prose generation requires editorial judgment, style decisions, and
authority that should rest with human reviewers and agency staff. BG
provides the structured, traceable layer that makes that step safe:

- Every evidence statement cites a source artifact and bundle ID.
- Confidence levels are derived from artifact readiness and completeness.
- Caveats are explicit and reusable by any downstream drafter.
- Follow-up questions are triggered by real evidence gaps, not boilerplate.

This design prevents hallucinated content from entering working papers and
ensures that every claim can be traced back to a governed BE or BF
artifact.

### Section Mapping Logic

BG populates eight fixed sections. Sections are never fabricated; empty
sections are marked `empty`.

| Section key | Content |
|---|---|
| `executive_summary` | Top critical/high ranked findings only |
| `study_objective` | Scenario summaries and declared study context |
| `technical_findings` | Core metric observations, threshold results |
| `comparative_results` | BF rankings and cross-run comparisons |
| `operational_implications` | High-priority findings in decision-relevant form |
| `limitations_and_caveats` | Completeness gaps, anomalies, mixed units, readiness limits |
| `agency_questions` | Follow-up questions triggered by caveats/anomalies/gaps |
| `recommended_next_steps` | Evidence-triggered bounded actions for error-severity caveats |

Each section carries a `synthesis_status` of `populated`, `partial`, or
`empty`.

### Confidence Semantics

| Level | Meaning |
|---|---|
| `high` | Evidence from a complete BE result with `ready_for_comparison`; or BF ranked results with ≥ 2 ready runs |
| `medium` | Evidence from a `limited_use` BE/BF artifact without hard errors |
| `low` | Evidence tied to partial completeness, anomalies, gaps, or readiness issues |

### Caveat and Follow-up Question Philosophy

Caveats are explicit, categorised, and carry severity levels so downstream
drafters can decide how to handle each one:

| Category | When raised |
|---|---|
| `data_gap` | A required metric is absent |
| `comparability_limit` | Mixed units prevented direct comparison |
| `anomaly` | A BF anomaly flag is present |
| `threshold_uncertainty` | A threshold assessment is `unknown` or `not_applicable` |
| `provenance_limit` | A run is marked `not_ready` |
| `modeling_limit` | Reserved for modeling-specific limits |

Follow-up questions are operational and evidence-triggered. They name the
specific metric, scenario, or artifact at issue. Generic filler questions
are not produced.

Examples of targeted questions BG will generate:
- "What additional inputs are needed to compute `path_loss_db` for bundle `bundle-001`?"
- "How should the anomaly in `interference_power_dbm` detected in `NRR-P2P-OUTLIER-001` be evaluated against operationally acceptable bounds?"
- "What threshold definition should govern `max_interference_dbm` for this study type?"

### Operator Workflow

**Step 1 — Run BE on each execution bundle:**
```
python scripts/run_output_evaluation.py <bundle_manifest.json>
```

**Step 2 — (Optional) Run BF to compare across runs:**
```
python scripts/cross_run_intelligence.py --input run1/nrr.json --input run2/nrr.json
```

**Step 3 — Run BG to synthesize evidence:**
```
python scripts/working_paper_synthesis.py \
    --be-input run1/normalized_run_result.json \
    --be-input run2/normalized_run_result.json \
    --bf-input comparison/cross_run_comparison.json \
    --output-dir outputs/evidence/
```

This writes `working_paper_evidence_pack.json` and
`working_paper_synthesis_decision.json` to `outputs/evidence/`. The
decision is also archived to `data/working_paper_synthesis_decisions/`.

**Exit codes:**
- `0` — pass: synthesis complete, no errors or warnings
- `1` — warning: synthesis complete with warning-level findings
- `2` — fail: missing or invalid inputs, schema failures, or error-level findings

### Artifact IDs and Patterns

| Artifact | ID prefix | Pattern |
|---|---|---|
| `working_paper_evidence_pack` | `WPE-` | `^WPE-[A-Z0-9][A-Z0-9._-]*$` |
| `working_paper_synthesis_decision` | `WPS-` | `^WPS-[A-Z0-9][A-Z0-9._-]*$` |
| Evidence pack | `EPK-` | `^EPK-[A-Z0-9][A-Z0-9._-]*$` |
| Evidence item | `EVI-` | `^EVI-[A-Z0-9][A-Z0-9._-]*$` |
| Ranked finding | `FND-` | `^FND-[A-Z0-9][A-Z0-9._-]*$` |
| Caveat | `CAV-` | `^CAV-[A-Z0-9][A-Z0-9._-]*$` |
| Follow-up question | `QST-` | `^QST-[A-Z0-9][A-Z0-9._-]*$` |

### Example: working_paper_evidence_pack (partial)

```json
{
  "artifact_id": "WPE-3A4B5C6D7E8F",
  "artifact_type": "working_paper_evidence_pack",
  "schema_version": "1.0.0",
  "evidence_pack_id": "EPK-1A2B3C4D5E6F",
  "study_type": "p2p_interference",
  "source_artifacts": [
    {
      "artifact_type": "normalized_run_result",
      "artifact_id": "NRR-P2P-RUN1-001",
      "source_bundle_id": "bundle-p2p-001",
      "path_or_reference": "run1/normalized_run_result.json"
    },
    {
      "artifact_type": "cross_run_comparison",
      "artifact_id": "CRC-BG-TEST-001",
      "source_bundle_id": "CMP-BG-TEST-001",
      "path_or_reference": "comparison/cross_run_comparison.json"
    }
  ],
  "section_evidence": [
    {
      "section_key": "technical_findings",
      "section_title": "Technical Findings",
      "synthesis_status": "populated",
      "evidence_items": [
        {
          "evidence_id": "EVI-A1B2C3D4E5F6",
          "evidence_type": "metric_observation",
          "statement": "Metric 'interference_power_dbm' = -85.3 dBm for scenario 'scenario-alpha' (bundle 'bundle-p2p-001').",
          "support": {
            "metric_name": "interference_power_dbm",
            "value": "-85.3",
            "unit": "dBm",
            "comparison_context": ""
          },
          "confidence": "high",
          "traceability": {
            "source_artifact_id": "NRR-P2P-RUN1-001",
            "source_bundle_id": "bundle-p2p-001",
            "source_path": "outputs/results_summary.json#interference_power_dbm"
          }
        }
      ]
    }
  ],
  "ranked_findings": [
    {
      "finding_id": "FND-B2C3D4E5F6A7",
      "priority": "high",
      "headline": "Top-ranked scenario on interference_power_dbm",
      "rationale": "Scenario 'scenario-alpha' ranks #1 descending on 'interference_power_dbm': value=-85.3.",
      "supporting_evidence_ids": ["EVI-A1B2C3D4E5F6"]
    }
  ],
  "caveats": [],
  "followup_questions": [],
  "generated_at": "2026-03-19T10:00:00+00:00"
}
```

### Example: working_paper_synthesis_decision

```json
{
  "artifact_type": "working_paper_synthesis_decision",
  "schema_version": "1.0.0",
  "decision_id": "WPS-C3D4E5F6A7B8",
  "evidence_pack_id": "EPK-1A2B3C4D5E6F",
  "overall_status": "pass",
  "failure_type": "none",
  "findings": [],
  "generated_at": "2026-03-19T10:00:00+00:00"
}
```
