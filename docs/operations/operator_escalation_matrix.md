# Operator Escalation Matrix

| Severity | Condition | Required Action |
| --- | --- | --- |
| normal | all monitored signals within normal thresholds | no action |
| warning | threshold approached or one warning-level signal | observe + log |
| freeze | unstable control state, fail-closed pause required | pause investigation |
| block | critical failure on trust/readiness/promotion path | stop + remediation required |

## Deterministic mapping anchors
- **Control outcomes**: `continue -> normal/warning`, `require_human_review -> freeze`, `stop/escalate -> block`.
- **Drift severity**: `none/warning -> normal|warning`, `freeze -> freeze`, `block -> block`.
- **Budget signals**: `healthy -> normal`, `warning -> warning`, `exhausted -> freeze|block` (block on critical path).
- **Readiness state**: `autonomous/supervised -> normal|warning`, `constrained -> freeze`, `unsafe -> block`.
