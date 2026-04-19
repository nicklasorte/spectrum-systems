# SLI Alert Response Runbook

## When eval_pass_rate WARNS (< 95%)

1. **Immediate (0-5 min)**
   - Check dashboard for trend: up/down/stable
   - View recent artifact failures in artifact_intelligence
   - Check if recent code changes: yes → potential cause

2. **Investigate (5-30 min)**
   - Query eval cases failing most: `SELECT eval_case_id, fail_count FROM eval_results WHERE status='fail' ORDER BY fail_count DESC LIMIT 10`
   - Check if specific eval case regressed (new test, new context)
   - Compare eval_pass_rate to model version history
   - Check if context bundle changed

3. **Decide (5-10 min)**
   - If eval case is flaky (< 10 failures): skip, monitor next cycle
   - If systematic (> 50 failures): escalate to team lead
   - If model change: check rollback feasibility
   - Record action in postmortem

4. **Close**
   - If WARN only: no action required, continue monitoring
   - If escalated: engineer investigates, opens PR/bug
   - Document finding in institutional_memory

## When eval_pass_rate FREEZES (< 85%)

1. **FREEZE_PIPELINE** immediately (automated)
2. **PAGE_ONCALL** (automated escalation)
3. **Create postmortem** with root cause
4. **Unfreeze only when** eval_pass_rate > 90% confirmed in 2 consecutive runs

## When drift_rate WARNS (> 1% per day)

1. Check upstream changes: model version, policy, eval cases added
2. Compare metric distribution to last 7-day baseline
3. If shift > 10%: investigate cause
4. If cause unknown: freeze and escalate
5. Document finding in institutional_memory
