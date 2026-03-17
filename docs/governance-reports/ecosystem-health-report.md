# Ecosystem Health Report

Generated: 2026-03-17T21:45:49Z  
Sources: `ecosystem/ecosystem-registry.json`, `governance/reports/contract-dependency-graph.json`, `artifacts/policy-engine-report.json`

**Overall Health**: ⚠️ `WARNING`

## Summary

| Metric | Value |
|--------|-------|
| Total Repos Inspected | 13 |
| Overall Health | ⚠️ warning |

## Governance Compliance

| Status | Count |
|--------|-------|
| ✅ compliant | 13 |
| ❌ fail | 0 |
| ⚠️ partial | 0 |
| ⚠️ warning | 0 |

## Contract Alignment

| Status | Count |
|--------|-------|
| 🏛 governance-repo | 1 |
| ✅ pass | 9 |
| ⚠️ warning | 3 |

## Schema Integrity

| Status | Count |
|--------|-------|
| ✅ compliant | 13 |

## CI Enforcement

| Status | Count |
|--------|-------|
| ✅ compliant | 7 |
| ❌ missing | 5 |
| ⚠️ partial | 1 |

## Repository Coverage

| Repo | Layer | System ID | Governance | Contract | Schema | CI | Maturity Level |
|------|-------|-----------|-----------|---------|--------|-----|----------------|
| `assumptions-registry-engine` | Layer 3 | assumptions-registry-engine | ✅ compliant | ✅ pass | ✅ compliant | ❌ missing | L6 |
| `comment-resolution-engine` | Layer 3 | comment-resolution-engine | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L10 |
| `docx-comment-injection-engine` | Layer 3 | docx-comment-injection-engine | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L10 |
| `knowledge-graph-engine` | Layer 3 | knowledge-graph-engine | ✅ compliant | ✅ pass | ✅ compliant | ❌ missing | L6 |
| `meeting-minutes-engine` | Layer 3 | meeting-minutes-engine | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L9 |
| `slide-intelligence-engine` | Layer 3 | slide-intelligence-engine | ✅ compliant | ✅ pass | ✅ compliant | ❌ missing | L6 |
| `spectrum-pipeline-engine` | Layer 4 | spectrum-pipeline-engine | ✅ compliant | ⚠️ warning | ✅ compliant | ❌ missing | L7 |
| `spectrum-program-advisor` | Layer 5 | spectrum-program-advisor | ✅ compliant | ⚠️ warning | ✅ compliant | ⚠️ partial | L8 |
| `spectrum-study-compiler` | Layer 3 | spectrum-study-compiler | ✅ compliant | ✅ pass | ✅ compliant | ❌ missing | L7 |
| `spectrum-systems` | Layer 2 | — | ✅ compliant | 🏛 governance-repo | ✅ compliant | ✅ compliant | L8 |
| `study-artifact-generator` | Layer 3 | study-artifact-generator | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L9 |
| `system-factory` | Layer 1 | system-factory | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L9 |
| `working-paper-review-engine` | Layer 3 | working-paper-review-engine | ✅ compliant | ⚠️ warning | ✅ compliant | ✅ compliant | L9 |

## Repos Missing Required Governance Artifacts

All repos with `manifest_required=true` have governance manifests. ✅

## Repos Not Yet Enforceable

All repos are enforceable (governance manifests present). ✅
