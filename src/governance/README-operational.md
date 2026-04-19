# Operational Guide

## Daily Checks

1. **SLI Status Dashboard**
   - Visit `/dashboard`
   - Check: all SLIs status = healthy?
   - Red flags: critical status, unusual trends

2. **Active Alerts**
   - Check escalation_events table for last 24h
   - Count: WARN (expected), FREEZE (investigate), BLOCK (urgent)

3. **Exception Backlog**
   - Should be < 5 active exceptions
   - If > 10: follow critical runbook

4. **Policy Health**
   - All policies with incidents = 0?
   - Rollout progress smooth (no spikes)?

## Weekly Tasks

1. **Drift Signal Review**
   - List unresolved drift signals > 7 days old
   - Investigate and mark resolved

2. **Exception Review**
   - Convert high-frequency exceptions to policies
   - Retire expired exceptions
   - Extend only if justified

3. **Judge Calibration**
   - Check reviewer_stats for drift alerts
   - Address approval_rate, consistency, bias outliers

4. **Postmortem Backlog**
   - Open postmortems due today?
   - Escalate overdue to team lead

## Monthly Tasks

1. **SLO Tuning**
   - Run SLOBaselineTuner for last 30 days
   - Compare to current targets
   - Adjust if confident (high confidence_level)

2. **A/B Testing**
   - Analyze running tests for winners
   - Promote winning policies to 100%
   - Deprecate losing policies

3. **Institutional Memory Review**
   - Precedents added last month: quality check
   - Supersede outdated precedents
   - Identify contradictions

4. **Capacity Planning**
   - Is cost_per_run trending up or down?
   - If up: investigate, optimize, or adjust target
   - If down: reinvest savings

## Escalation Paths

**WARN** (log):
- No immediate action required
- Monitor in next cycle

**FREEZE** (alert, 30 min response):
- Team lead notified
- Engineering lead investigates
- Update postmortem with status

**BLOCK** (page, 5 min response):
- On-call engineer + team lead + manager notified
- Critical incident response
- War room if needed

## Recovery Procedures

See dedicated runbooks:
- `sli-alert-response.md` — eval_pass_rate, drift_rate alerts
- `exception-backlog-critical.md` — too many manual exceptions
- `policy-incident-recovery.md` — policy rollback/redeployment
