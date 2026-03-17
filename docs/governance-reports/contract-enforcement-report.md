# Cross-Repo Contract Enforcement Report

Generated: 2026-03-17T05:54:23Z
Source: `contracts/standards-manifest.json`

## Summary

| Status | Count |
|--------|-------|
| Pass | 7 |
| Fail | 0 |
| Warning | 2 |
| Not Yet Enforceable | 0 |
| Total Inspected | 10 |

## Repos Inspected

- **comment-resolution-engine** `comment-resolution-engine` — ✅ PASS
- **docx-comment-injection-engine** `docx-comment-injection-engine` — ✅ PASS
- **meeting-minutes-engine** `meeting-minutes-engine` — ⚠️ WARNING
- **spectrum-pipeline-engine** `spectrum-pipeline-engine` — ✅ PASS
- **spectrum-program-advisor** `spectrum-program-advisor` — ⚠️ WARNING
- **spectrum-study-compiler** `spectrum-study-compiler` — ✅ PASS
- **spectrum-systems** — 🏛 GOVERNANCE REPO
- **study-artifact-generator** `study-artifact-generator` — ✅ PASS
- **system-factory** `system-factory` — ✅ PASS
- **working-paper-review-engine** `working-paper-review-engine` — ✅ PASS

## Enforcement Failures

None.

## Warnings

- `[contract-enforcement] repo=meeting-minutes-engine system_id=meeting-minutes-engine contract=meeting_minutes_record rule=consumer-consistency error=repo is listed as intended_consumer of 'meeting_minutes_record' (canonical v1.0.0) but does not declare it in its governance manifest`
- `[contract-enforcement] repo=spectrum-program-advisor system_id=spectrum-program-advisor contract=meeting_minutes_record rule=consumer-consistency error=repo is listed as intended_consumer of 'meeting_minutes_record' (canonical v1.0.0) but does not declare it in its governance manifest`

## Not Yet Enforceable

All governed repos have governance manifests.

## Remediation Actions

### Warnings (recommended)
- **meeting-minutes-engine**: `consumer-consistency` on `meeting_minutes_record` — repo is listed as intended_consumer of 'meeting_minutes_record' (canonical v1.0.0) but does not declare it in its governance manifest.
- **spectrum-program-advisor**: `consumer-consistency` on `meeting_minutes_record` — repo is listed as intended_consumer of 'meeting_minutes_record' (canonical v1.0.0) but does not declare it in its governance manifest.

