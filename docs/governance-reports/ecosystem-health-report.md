# Ecosystem Health Report

Generated: 2026-04-30T09:59:56Z  
Sources: `ecosystem/ecosystem-registry.json`, `governance/reports/contract-dependency-graph.json`, `artifacts/policy-engine-report.json`

**Overall Health**: ⚠️ `WARNING`

## Summary

| Metric | Value |
|--------|-------|
| Total Repos Inspected | 15 |
| Overall Health | ⚠️ warning |

## Governance Compliance

| Status | Count |
|--------|-------|
| ✅ compliant | 12 |
| ❌ fail | 0 |
| ⚠️ partial | 0 |
| ⚠️ warning | 3 |

## Contract Alignment

| Status | Count |
|--------|-------|
| 🏛 governance-repo | 2 |
| ✅ pass | 13 |

## Schema Integrity

| Status | Count |
|--------|-------|
| ✅ compliant | 15 |

## CI Compliance Observations

| Status | Count |
|--------|-------|
| ✅ compliant | 8 |
| ❌ missing | 6 |
| ⚠️ partial | 1 |

## Repository Coverage

| Repo | Layer | System ID | Governance | Contract | Schema | CI | Maturity Level |
|------|-------|-----------|-----------|---------|--------|-----|----------------|
| `assumptions-registry-engine` | Layer 3 | assumptions-registry-engine | ✅ compliant | ✅ pass | ✅ compliant | ❌ missing | L6 |
| `comment-resolution-engine` | Layer 3 | comment-resolution-engine | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L10 |
| `docx-comment-injection-engine` | Layer 3 | docx-comment-injection-engine | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L10 |
| `governed-prompt-queue` | Layer 4 | governed-prompt-queue | ✅ compliant | ✅ pass | ✅ compliant | ❌ missing | L6 |
| `knowledge-graph-engine` | Layer 3 | knowledge-graph-engine | ✅ compliant | ✅ pass | ✅ compliant | ❌ missing | L6 |
| `meeting-minutes-engine` | Layer 3 | meeting-minutes-engine | ⚠️ warning | ✅ pass | ✅ compliant | ✅ compliant | L9 |
| `slide-intelligence-engine` | Layer 3 | slide-intelligence-engine | ✅ compliant | ✅ pass | ✅ compliant | ❌ missing | L6 |
| `spectrum-pipeline-engine` | Layer 4 | spectrum-pipeline-engine | ✅ compliant | ✅ pass | ✅ compliant | ❌ missing | L8 |
| `spectrum-program-advisor` | Layer 5 | spectrum-program-advisor | ⚠️ warning | ✅ pass | ✅ compliant | ⚠️ partial | L9 |
| `spectrum-study-compiler` | Layer 3 | spectrum-study-compiler | ✅ compliant | ✅ pass | ✅ compliant | ❌ missing | L7 |
| `spectrum-systems` | Layer 2 | — | ⚠️ warning | 🏛 governance-repo | ✅ compliant | ✅ compliant | L8 |
| `study-artifact-generator` | Layer 3 | study-artifact-generator | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L9 |
| `system-factory` | Layer 1 | system-factory | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L9 |
| `tlc` | Layer 2 | — | ✅ compliant | 🏛 governance-repo | ✅ compliant | ✅ compliant | L7 |
| `working-paper-review-engine` | Layer 3 | working-paper-review-engine | ✅ compliant | ✅ pass | ✅ compliant | ✅ compliant | L10 |

## Repos Missing Required Governance Artifacts

All repos with `manifest_required=true` have governance manifests. ✅

## Repos Not Yet Enforceable

All repos are enforceable (governance manifests present). ✅
