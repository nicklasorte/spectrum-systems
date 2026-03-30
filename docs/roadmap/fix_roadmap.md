# Fix Roadmap

Cycle: `cycle-0001`

## Summary
- blocker: 1
- required_fix: 1
- optional_improvement: 1
- total_unique_findings: 3

## Bundles
### bundle-blocker-001 (blocker)
- rationale: Grouped by shared repository seam and dependency proximity; same seam implies minimum coherent PQX bundle with reduced cross-module churn.
- target_seams: spectrum_systems/orchestration
- [f-001] Runner should guard approval (critical) — reviewers: claude, codex

### bundle-required_fix-002 (required_fix)
- rationale: Grouped by shared repository seam and dependency proximity; same seam implies minimum coherent PQX bundle with reduced cross-module churn.
- target_seams: tests/test_cycle_runner.py
- [f-004] Add schema validation test (medium) — reviewers: codex

### bundle-optional_improvement-003 (optional_improvement)
- rationale: Grouped by shared repository seam and dependency proximity; same seam implies minimum coherent PQX bundle with reduced cross-module churn.
- target_seams: docs/architecture
- [f-002] Contract docs link is stale (low) — reviewers: claude

