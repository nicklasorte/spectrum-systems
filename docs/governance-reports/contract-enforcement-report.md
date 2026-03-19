# Cross-Repo Contract Enforcement Report

Generated: 2026-03-19T19:48:59Z
Source: `contracts/standards-manifest.json`

## Summary

| Status | Count |
|--------|-------|
| Pass | 9 |
| Fail | 0 |
| Warning | 3 |
| Not Yet Enforceable | 0 |
| Total Inspected | 13 |

## Repos Inspected

- **assumptions-registry-engine** `assumptions-registry-engine` — ✅ PASS
- **comment-resolution-engine** `comment-resolution-engine` — ✅ PASS
- **docx-comment-injection-engine** `docx-comment-injection-engine` — ✅ PASS
- **knowledge-graph-engine** `knowledge-graph-engine` — ✅ PASS
- **meeting-minutes-engine** `meeting-minutes-engine` — ✅ PASS
- **slide-intelligence-engine** `slide-intelligence-engine` — ✅ PASS
- **spectrum-pipeline-engine** `spectrum-pipeline-engine` — ⚠️ WARNING
- **spectrum-program-advisor** `spectrum-program-advisor` — ⚠️ WARNING
- **spectrum-study-compiler** `spectrum-study-compiler` — ✅ PASS
- **spectrum-systems** — 🏛 GOVERNANCE REPO
- **study-artifact-generator** `study-artifact-generator` — ✅ PASS
- **system-factory** `system-factory` — ✅ PASS
- **working-paper-review-engine** `working-paper-review-engine` — ⚠️ WARNING

## Enforcement Failures

None.

## Warnings

- `[contract-enforcement] repo=spectrum-pipeline-engine system_id=spectrum-pipeline-engine contract=evaluation_manifest rule=consumer-consistency error=repo is listed as intended_consumer of 'evaluation_manifest' (canonical v1.0.0) but does not declare it in its governance manifest`
- `[contract-enforcement] repo=spectrum-program-advisor system_id=spectrum-program-advisor contract=evaluation_manifest rule=consumer-consistency error=repo is listed as intended_consumer of 'evaluation_manifest' (canonical v1.0.0) but does not declare it in its governance manifest`
- `[contract-enforcement] repo=working-paper-review-engine system_id=working-paper-review-engine contract=slide_deck rule=consumer-consistency error=repo is listed as intended_consumer of 'slide_deck' (canonical v1.0.0) but does not declare it in its governance manifest`
- `[contract-enforcement] repo=spectrum-pipeline-engine system_id=spectrum-pipeline-engine contract=slide_deck rule=consumer-consistency error=repo is listed as intended_consumer of 'slide_deck' (canonical v1.0.0) but does not declare it in its governance manifest`
- `[contract-enforcement] repo=working-paper-review-engine system_id=working-paper-review-engine contract=slide_intelligence_packet rule=consumer-consistency error=repo is listed as intended_consumer of 'slide_intelligence_packet' (canonical v1.0.0) but does not declare it in its governance manifest`
- `[contract-enforcement] repo=spectrum-program-advisor system_id=spectrum-program-advisor contract=slide_intelligence_packet rule=consumer-consistency error=repo is listed as intended_consumer of 'slide_intelligence_packet' (canonical v1.0.0) but does not declare it in its governance manifest`

## Not Yet Enforceable

All governed repos have governance manifests.

## Remediation Actions

### Warnings (recommended)
- **spectrum-pipeline-engine**: `consumer-consistency` on `evaluation_manifest` — repo is listed as intended_consumer of 'evaluation_manifest' (canonical v1.0.0) but does not declare it in its governance manifest.
- **spectrum-program-advisor**: `consumer-consistency` on `evaluation_manifest` — repo is listed as intended_consumer of 'evaluation_manifest' (canonical v1.0.0) but does not declare it in its governance manifest.
- **working-paper-review-engine**: `consumer-consistency` on `slide_deck` — repo is listed as intended_consumer of 'slide_deck' (canonical v1.0.0) but does not declare it in its governance manifest.
- **spectrum-pipeline-engine**: `consumer-consistency` on `slide_deck` — repo is listed as intended_consumer of 'slide_deck' (canonical v1.0.0) but does not declare it in its governance manifest.
- **working-paper-review-engine**: `consumer-consistency` on `slide_intelligence_packet` — repo is listed as intended_consumer of 'slide_intelligence_packet' (canonical v1.0.0) but does not declare it in its governance manifest.
- **spectrum-program-advisor**: `consumer-consistency` on `slide_intelligence_packet` — repo is listed as intended_consumer of 'slide_intelligence_packet' (canonical v1.0.0) but does not declare it in its governance manifest.

