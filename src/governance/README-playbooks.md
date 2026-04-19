# Playbook Registry + Escalation Engine

## Playbook Registry

Maps reason codes and signal types to response workflows.

### Built-in Playbooks

- **drift_metric_distribution**: Investigate SLI metric shifts > 10%
  - Steps: investigate upstream, compare to baseline, freeze or continue
  - Owner: SRE

- **exception_accumulation_critical**: Handle > 10 active exceptions
  - Steps: freeze promotion, alert lead, review backlog, unfreeze
  - Owner: Engineering Lead

- **eval_pass_rate_block**: Handle eval pass rate < 90%
  - Steps: block promotion, create postmortem, investigate, fix, verify
  - Owner: On-Call Engineer

## Escalation Engine

Routes alerts based on severity level:

- **WARN** (log): Log to console, no alert
- **FREEZE** (alert): Email ops team
- **BLOCK** (page): Page on-call engineer + team lead

Integration: After control loop decision "freeze" or "block", escalation engine determines who to notify and follows playbook.

## Execution Tracking

All playbook executions are tracked:
- Execution ID links signal → playbook → steps
- Each step records: executor, start time, outcome, notes
- Full audit trail for governance

## Enhanced Escalation Context

Escalation events include:
- Artifact ID and trace link
- Current value vs. baseline
- Percentage shift calculation
- Dashboard deep-link for investigation
- Historical trend data (when available)

## Acknowledgment

Escalation events track acknowledgment:
- sent: Initial alert dispatched
- acknowledged: Team lead confirmed receipt
- failed: Failed to deliver to channel
