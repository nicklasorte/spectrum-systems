# Top Failure Modes Dashboard Review

This review mirrors `failure_mode_dashboard_record` and highlights top 10 current failure modes across active 3LS systems.

## Top 10
1. Promotion attempt without eval evidence.
2. Unknown state path accepted by parser without escalation.
3. Missing lineage chain for closure candidates.
4. Stale policy version used at trust adjudication.
5. Fake healthy telemetry masking degraded enforcement.
6. Context bundle conflict not resolved before PQX execution.
7. Rollback trigger declared but rollback artifact not emitted.
8. Human override performed without override artifact.
9. Replay package incomplete for postmortem.
10. Capacity saturation causing delayed enforcement actions.

See `contracts/examples/failure_mode_dashboard_record.example.json` for structured severity, trend, detection, control response, and fix status.
