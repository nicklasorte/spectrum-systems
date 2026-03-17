# Evaluation Spine Report

Generated: 2026-03-17T05:51:20Z  
Source: spectrum-systems governance repository  
Scope: Prompt J — Evidence & Evaluation Spine

---

## Summary

This report documents the evaluation spine artifacts introduced in spectrum-systems. The evaluation spine is the canonical framework for recording evidence, evaluating outputs, and assessing readiness across the spectrum ecosystem.

---

## Artifact Types Introduced

| Artifact Type | Schema Location | Example Location | Authority |
|---|---|---|---|
| `evaluation_manifest` | `contracts/schemas/evaluation_manifest.schema.json` | `contracts/examples/evaluation_manifest.json` | spectrum-systems (canonical) |
| `readiness_assessment` | `governance/schemas/readiness_assessment.schema.json` | `governance/examples/evidence-bundle/readiness_assessment.json` | spectrum-systems (canonical) |

### Pre-existing Evidence Bundle Artifacts (Normalized)

| Artifact Type | Schema Location | Example Location |
|---|---|---|
| `run_manifest` | `governance/schemas/run_manifest.schema.json` | `governance/examples/evidence-bundle/run_manifest.json` |
| `evaluation_results` | `governance/schemas/evaluation_results.schema.json` | `governance/examples/evidence-bundle/evaluation_results.json` |
| `provenance` | `governance/schemas/provenance.schema.json` | `governance/examples/evidence-bundle/provenance.json` |
| `contract_validation_report` | `governance/schemas/contract_validation_report.schema.json` | `governance/examples/evidence-bundle/contract_validation_report.json` |

---

## Evaluation Status Vocabulary

| Status | Meaning | When to Use |
|---|---|---|
| `pass` | All required checks passed | Run or output met all criteria |
| `fail` | One or more checks failed | Blocking issue detected; criteria_applied must be non-empty |
| `warning` | Checks passed with anomalies | Incomplete coverage, missing optional evidence, or degraded quality |
| `not-yet-evaluable` | Evidence not yet available | Run is recorded but evaluation must be deferred |

---

## Readiness Model

| Level | Meaning | Enforcement |
|---|---|---|
| `draft` | In progress; no downstream consumption | None |
| `internal-review` | Complete enough for internal review | None |
| `cross-engine-ready` | Validated for cross-engine consumption | None |
| `governance-ready` | Validated against governance contracts | Requires at least one `evidence_ref` |
| `decision-support-ready` | Suitable for program decisions | Requires at least one `evidence_ref` |

---

## Validation Expectations

### Schema Validation

All evaluation manifests must validate against `contracts/schemas/evaluation_manifest.schema.json`.  
All readiness assessments must validate against `governance/schemas/readiness_assessment.schema.json`.

Use the provided script:

```bash
python scripts/validate_evaluation_manifest.py path/to/evaluation_manifest.json
```

### Evidence Integrity Checks

The validation script enforces:

1. All `evidence_refs` entries have `ref_type` and `ref_id` fields.
2. `ref_type` must be one of the allowed enum values in the schema.
3. When `--bundle` is provided, `ref_path` values are verified on disk.

### Semantic Readiness Rules

The validation script additionally enforces:

1. `governance-ready` and `decision-support-ready` require at least one `evidence_ref`.
2. `status == 'fail'` requires a non-empty `criteria_applied` list.

---

## Current Example Artifacts

| Artifact | Path | run_id |
|---|---|---|
| Evaluation Manifest | `contracts/examples/evaluation_manifest.json` | `run-20260315T175500Z` |
| Readiness Assessment | `governance/examples/evidence-bundle/readiness_assessment.json` | `RUN-2026-03-15-PIPE-001` |
| Run Manifest | `governance/examples/evidence-bundle/run_manifest.json` | `RUN-2026-03-15-PIPE-001` |
| Evaluation Results | `governance/examples/evidence-bundle/evaluation_results.json` | `RUN-2026-03-15-PIPE-001` |
| Provenance Record | `governance/examples/evidence-bundle/provenance.json` | `RUN-2026-03-15-PIPE-001` |
| Contract Validation Report | `governance/examples/evidence-bundle/contract_validation_report.json` | `RUN-2026-03-15-PIPE-001` |

---

## Integration Notes

### Prompt H (Observability)

- Consume `readiness_assessment.json` from evidence bundles to surface readiness level per system in ecosystem health reports.
- Surface `evaluation_summary` pass/fail/warning counts in health dashboards.
- Flag systems without a readiness assessment as `not-yet-evaluable` in health reports.

### Prompt I (Pipeline Engine)

- Emit `readiness_assessment.json` as part of every evidence bundle.
- Emit `evaluation_manifest.json` after each pipeline run.
- Use `run_id` consistently across all artifacts in the bundle.
- Validate manifests in CI using `scripts/validate_evaluation_manifest.py`.

---

## Test Coverage

Tests for the evaluation spine are in `tests/test_evaluation_spine.py` and cover:

- Schema file existence (evaluation_manifest, readiness_assessment)
- Documentation file existence (evaluation-spine.md, this report)
- Schema self-validity (both schemas are valid JSON Schemas)
- Valid example artifacts pass schema validation
- Missing required fields are rejected
- Invalid `status` values are rejected
- Invalid `readiness_level` values are rejected
- Malformed `evidence_refs` are detected
- Validation script functions (validate_schema, validate_evidence_refs, validate_readiness_requirements, validate_manifest)
