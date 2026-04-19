# MVP-to-Governance Integration

Connects MVPs (1-13) to Phase 2 storage and Phase 3 governance.

## Flow

1. **MVP-3**: Emit transcript_eval_baseline → record to SLI backend
2. **MVP-6**: Emit extraction results → record extraction_quality SLI
3. **MVP-9**: Emit draft → record draft_quality_score SLI
4. **MVP-13**: Emit certification artifact → record cost_per_run, trace_coverage
5. **All Steps**: Emit lineage edges → record in Phase 3 lineage graph
6. **Release Gate**: Query control signals → decide allow/warn/freeze/block

## SLI Recording Points

- MVP-3 → transcript_eval_baseline
- MVP-4 → extraction_quality_minutes
- MVP-5 → extraction_quality_issues
- MVP-6 → eval_gate_pass_rate
- MVP-8 → draft_quality_score
- MVP-9 → draft_quality_eval_pass
- MVP-10 → review_completion_rate
- MVP-11 → revision_quality_score
- MVP-13 → cost_per_run, trace_coverage

## Release Gates

After MVP-13 certification:
1. Check SLI alerts (if eval_pass_rate < 90% → BLOCK)
2. Check drift signals (if critical → WARN)
3. Check exception backlog (if critical → FREEZE)
4. Check policy incidents (if > threshold → FREEZE)
5. If all clear → allow promotion

## Control Decision Artifact

CI/orchestration queries control signals, creates decision artifact:
```json
{
  "artifact_kind": "control_decision",
  "target_artifact_id": "spectrum-study-123",
  "decision": "allow" | "warn" | "freeze" | "block",
  "reason_codes": ["eval_passed", "no_drift_signals"],
  "created_by": "ci_orchestration"
}
```
