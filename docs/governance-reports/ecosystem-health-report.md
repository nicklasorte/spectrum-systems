# Ecosystem Health Report

Generated: 2026-03-17T13:26:54Z  
Sources: `ecosystem/ecosystem-registry.json`, `governance/reports/contract-dependency-graph.json`, `artifacts/policy-engine-report.json`

**Overall Health**: ⚠️ `WARNING`

## Summary

| Metric | Value |
|--------|-------|
| Total Repos Inspected | 10 |
| Overall Health | ⚠️ warning |

## Governance Compliance

| Status | Count |
|--------|-------|
| ✅ compliant | 9 |
| ❌ fail | 0 |
| ⚠️ partial | 0 |
| ⚠️ warning | 1 |

## Contract Alignment

| Status | Count |
|--------|-------|
| 🏛 governance-repo | 1 |
| ✅ pass | 6 |
| ⚠️ warning | 3 |

## Schema Integrity

| Status | Count |
|--------|-------|
| ✅ compliant | 10 |

## CI Enforcement

| Status | Count |
|--------|-------|
| ✅ compliant | 7 |
| ❌ missing | 2 |
| ⚠️ partial | 1 |

## Repository Coverage

| Repo | Layer | System ID | Governance | Contract | Schema | CI | Maturity Level |
|------|-------|-----------|-----------|---------|--------|-----|----------------|
| `comment-resolution-engine` | Layer 3 | comment-resolution-engine | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L10 |
| `docx-comment-injection-engine` | Layer 3 | docx-comment-injection-engine | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L10 |
| `meeting-minutes-engine` | Layer 3 | meeting-minutes-engine | ✅ compliant | ⚠️ warning | ✅ compliant | ✅ compliant | L8 |
| `spectrum-pipeline-engine` | Layer 4 | spectrum-pipeline-engine | ✅ compliant | ⚠️ warning | ✅ compliant | ❌ missing | L7 |
| `spectrum-program-advisor` | Layer 5 | spectrum-program-advisor | ✅ compliant | ⚠️ warning | ✅ compliant | ⚠️ partial | L8 |
| `spectrum-study-compiler` | Layer 3 | spectrum-study-compiler | ✅ compliant | ✅ pass | ✅ compliant | ❌ missing | L7 |
| `spectrum-systems` | Layer 2 | — | ⚠️ warning | 🏛 governance-repo | ✅ compliant | ✅ compliant | L8 |
| `study-artifact-generator` | Layer 3 | study-artifact-generator | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L9 |
| `system-factory` | Layer 1 | system-factory | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L9 |
| `working-paper-review-engine` | Layer 3 | working-paper-review-engine | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L10 |

## Repos Missing Required Governance Artifacts

All repos with `manifest_required=true` have governance manifests. ✅

## Repos Not Yet Enforceable

All repos are enforceable (governance manifests present). ✅
