# Evaluation Spine

The evaluation spine is the canonical evidence and evaluation framework for the spectrum ecosystem. It lives in `spectrum-systems` because spectrum-systems is the governance authority — all downstream repos (pipeline engines, study compilers, advisor repos) inherit evaluation standards from here.

---

## What the Evaluation Spine Is

The evaluation spine defines:

1. **How pipeline runs, engine outputs, and governed artifacts are evaluated** — via explicit check criteria, pass/fail/warning/not-yet-evaluable semantics, and machine-readable results.
2. **How evidence is recorded** — via a standard evidence bundle structure (run manifest, evaluation results, provenance, contract validation report, readiness assessment).
3. **How readiness is assessed** — via a five-level readiness model that downstream repos can use as a shared vocabulary.

All artifacts are schema-backed, deterministic, and git-friendly. No external network calls are needed.

---

## Why It Lives in spectrum-systems

spectrum-systems is the canonical governance and contract authority for the ecosystem. Downstream repos must not invent their own evaluation or readiness semantics — they must emit artifacts that conform to the schemas defined here. This ensures that:

- Governance observability (Prompt H) can consume evaluation status uniformly across all repos.
- Pipeline outputs (Prompt I) can produce evidence artifacts that any downstream consumer can parse.
- Future engines and advisor repos have a clear, tested target.

---

## Artifact Types

### Evaluation Manifest

**Schema**: `contracts/schemas/evaluation_manifest.schema.json`  
**Example**: `contracts/examples/evaluation_manifest.json`  
**Purpose**: Top-level evaluation record linking a run or artifact set to its evidence, criteria, results summary, and readiness status.

| Field | Required | Description |
|---|---|---|
| `artifact_type` | ✅ | Must be `"evaluation_manifest"` |
| `artifact_id` | ✅ | Pattern `^EVAL-[A-Z0-9._-]+$` |
| `artifact_version` | ✅ | Semver string |
| `schema_version` | ✅ | Must be `"1.0.0"` |
| `standards_version` | ✅ | Must be `"2026.03.0"` |
| `record_id` | ✅ | Pattern `^REC-[A-Z0-9._-]+$` |
| `run_id` | ✅ | Deterministic run identifier |
| `created_at` | ✅ | ISO 8601 timestamp |
| `created_by` | ✅ | Agent producing this manifest |
| `source_repo` | ✅ | Repo where the evaluated run was produced |
| `source_repo_version` | ✅ | Git ref at evaluation time |
| `system_id` | ✅ | Ecosystem registry system identifier |
| `evaluation_type` | ✅ | `pipeline_run`, `engine_output`, `review_artifact`, or `advisor_output` |
| `evaluation_date` | ✅ | ISO 8601 timestamp of evaluation |
| `evaluator` | ✅ | Agent that performed the evaluation |
| `criteria_applied` | ✅ | Non-empty list of check names |
| `artifact_set` | ✅ | Artifacts evaluated (id, type, optional path) |
| `results_summary` | ✅ | `total_checks`, `passed`, `failed`, `warnings` |
| `status` | ✅ | See Evaluation Status Vocabulary below |
| `readiness_level` | ✅ | See Readiness Model below |
| `evidence_refs` | ✅ | References to evidence bundle artifacts |
| `notes` | — | Freeform context or caveats |

### Readiness Assessment (Governance-level)

**Schema**: `governance/schemas/readiness_assessment.schema.json`  
**Example**: `governance/examples/evidence-bundle/readiness_assessment.json`  
**Purpose**: Lightweight operational record emitted inside an evidence bundle. Records readiness level, blocking items, and pointers to supporting evidence. Simpler than the full evaluation manifest; intended for direct emission by engines.

| Field | Required | Description |
|---|---|---|
| `run_id` | ✅ | Run identifier |
| `system_id` | ✅ | Ecosystem registry system identifier |
| `evaluated_at` | ✅ | ISO 8601 timestamp |
| `readiness_level` | ✅ | See Readiness Model below |
| `evaluation_summary` | ✅ | Pass/fail/warning counts |
| `blocking_items` | — | Items preventing advancement |
| `evidence_refs` | — | Pointers to supporting evidence |
| `notes` | — | Freeform context |

### Existing Evidence Bundle Artifacts

The following artifacts are defined by earlier governance work and are part of the evaluation spine:

| Artifact | Schema | Purpose |
|---|---|---|
| Run Manifest | `governance/schemas/run_manifest.schema.json` | Records inputs, outputs, timing, and environment for a governed run |
| Evaluation Results | `governance/schemas/evaluation_results.schema.json` | Per-check evaluation records with pass/fail/warn and metrics |
| Provenance Record | `governance/schemas/provenance.schema.json` | Lineage record linking generated artifacts to source artifacts and contracts |
| Contract Validation Report | `governance/schemas/contract_validation_report.schema.json` | Per-artifact contract compliance result |

---

## Evaluation Status Vocabulary

| Status | Meaning |
|---|---|
| `pass` | All required checks passed; no blocking issues |
| `fail` | One or more required checks failed; advancement is blocked |
| `warning` | Checks passed but anomalies or incomplete coverage were detected |
| `not-yet-evaluable` | Required evidence or prerequisites are not yet available; evaluation is deferred |

**Enforcement rule**: A `status` of `fail` requires a non-empty `criteria_applied` list so the failure is traceable. A `status` of `not-yet-evaluable` does not block a run from being recorded; it signals that evaluation should be retried when evidence is available.

---

## Readiness Model

| Level | Meaning |
|---|---|
| `draft` | Artifact or run is in progress; not ready for any downstream consumption |
| `internal-review` | Output is complete enough for internal review within the producing team; not yet ready for cross-engine consumption |
| `cross-engine-ready` | Output has passed internal checks and is ready for consumption by other engines in the pipeline |
| `governance-ready` | Output has been validated against governance contracts and is ready for inclusion in governed reports |
| `decision-support-ready` | Output has passed all gates and is suitable for use in program or spectrum management decisions |

**Enforcement rule**: `governance-ready` and `decision-support-ready` require at least one `evidence_ref` to substantiate the claim.

**Anti-pattern**: Do not use readiness levels to manufacture false precision. If evidence is missing, use `draft` or `internal-review` rather than claiming a higher level.

---

## How Pipeline and Engine Repos Should Adopt This Framework

### Emitting an Evidence Bundle

At the end of every governed run, emit an evidence bundle directory containing:

```
evidence-bundle/
  run_manifest.json             ← governed by governance/schemas/run_manifest.schema.json
  evaluation_results.json       ← governed by governance/schemas/evaluation_results.schema.json
  contract_validation_report.json ← governed by governance/schemas/contract_validation_report.schema.json
  provenance.json               ← governed by governance/schemas/provenance.schema.json
  readiness_assessment.json     ← governed by governance/schemas/readiness_assessment.schema.json
```

All five artifacts must share the same `run_id`.

### Emitting an Evaluation Manifest

After producing an evidence bundle, emit an evaluation manifest:

```
evaluation_manifest.json        ← governed by contracts/schemas/evaluation_manifest.schema.json
```

The evaluation manifest references the evidence bundle artifacts via `evidence_refs`. Use `ref_type` values from the allowed enum:
`run_manifest`, `evaluation_results`, `provenance`, `contract_validation_report`, `readiness_assessment`, `external`.

### Validating the Evaluation Manifest

Use the provided validation script:

```bash
python scripts/validate_evaluation_manifest.py path/to/evaluation_manifest.json \
  --bundle path/to/evidence-bundle/
```

The script validates the manifest against the canonical schema, checks evidence_ref well-formedness, verifies ref_path existence if `--bundle` is provided, and enforces semantic readiness rules.

---

## How Observability Should Consume Evaluation Outputs

The governance observability layer (Prompt H) can consume evaluation status from:

1. **`readiness_assessment.json`** in an evidence bundle — for per-run readiness level and blocking item reporting.
2. **`evaluation_results.json`** in an evidence bundle — for per-check pass/fail/warn counts.
3. **`evaluation_manifest.json`** — for the authoritative evaluation record with full evidence linkage.

Observability tooling should ingest these artifacts by `run_id` and surface `readiness_level` and `status` in health dashboards and compliance reports without re-evaluating the underlying artifacts.

---

## Validation Script

**Script**: `scripts/validate_evaluation_manifest.py`

Functions exposed (importable):

| Function | Purpose |
|---|---|
| `validate_schema(instance)` | Validate a manifest dict against the JSON Schema; returns error list |
| `validate_evidence_refs(instance, bundle_path)` | Check evidence_refs for required fields and optional disk existence |
| `validate_readiness_requirements(instance)` | Enforce semantic readiness rules |
| `validate_manifest(manifest_path, bundle_path)` | Full pipeline; returns result dict with `status` and `errors` |

---

## Example Artifacts

| Artifact | Path |
|---|---|
| Evaluation manifest example | `contracts/examples/evaluation_manifest.json` |
| Readiness assessment example | `governance/examples/evidence-bundle/readiness_assessment.json` |
| Run manifest example | `governance/examples/evidence-bundle/run_manifest.json` |
| Evaluation results example | `governance/examples/evidence-bundle/evaluation_results.json` |
| Provenance example | `governance/examples/evidence-bundle/provenance.json` |
| Contract validation report example | `governance/examples/evidence-bundle/contract_validation_report.json` |

---

## Integration Notes

### Prompt H (Observability)

The observability layer should:
- Ingest `readiness_assessment.json` from evidence bundles per run.
- Surface `readiness_level` and `evaluation_summary` in the ecosystem health report.
- Flag runs without a `readiness_assessment.json` as incomplete in the health dashboard.

### Prompt I (Pipeline Engine)

The pipeline engine should:
- Emit a `readiness_assessment.json` as part of every evidence bundle.
- Emit an `evaluation_manifest.json` after each pipeline run, referencing the evidence bundle artifacts.
- Use `run_id` consistently across all evidence bundle artifacts.
- Use the `validate_evaluation_manifest.py` script in CI to verify emitted manifests.

---

## Recommended Next Steps

1. Add `readiness_assessment.json` to the standard evidence bundle in `scripts/validate_run_evidence_bundle.py` once the pipeline engine is ready to emit it.
2. Update `scripts/generate_ecosystem_health_report.py` to ingest `readiness_level` from evidence bundles.
3. Add per-system readiness tracking to `governance/reports/ecosystem-health.json`.
4. Define an ADR for the evaluation spine if the readiness model is challenged during cross-engine adoption.
