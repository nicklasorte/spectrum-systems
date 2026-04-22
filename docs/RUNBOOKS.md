# Spectrum Systems Dashboard Runbooks

## RB-1: Dashboard Uptime Alert

**Trigger**: Health check fails 2x in a row (10 minute window)

**Diagnosis**:
1. Check Vercel dashboard: https://vercel.com (is deployment up?)
2. Check artifact API: `curl https://api.spectrum-systems.com/health`
3. Check error logs: Sentry dashboard

**Resolution**:
- If Vercel down: Wait for auto-recovery or contact Vercel support
- If artifact API down: Check artifact store health, restart if needed
- If code error: Rollback to previous deployment

## RB-2: Control Decision "BLOCK" Fired

**Trigger**: Dashboard shows control_decisions = ["block"]

**Meaning**: System entropy critical, all promotions should stop

**Immediate Actions** (first 5 minutes):
1. Page on-call governance lead
2. Notify team in #incidents Slack channel
3. Gather recent changes: `git log --oneline -10`

**Investigation** (next 15 minutes):
1. Check which metric(s) triggered block:
   - Decision divergence > 20%?
   - Exception rate > 5%?
   - Trace coverage < SLO?
2. Query reason codes: A1 query shows top failure reasons
3. Review incidents: Any recent deployments?

**Resolution**:
- If bad deployment: Rollback immediately
- If transient spike: Monitor for recovery (next 5 minutes)
- If persistent: Escalate to governance council, declare incident

## RB-3: Query Timeout (> 5s)

**Trigger**: Query p99 latency exceeds 5 seconds

**Diagnosis**:
1. Which query is slow? Check dashboard metrics
2. Check artifact API: `curl -I https://api.spectrum-systems.com/health`
3. Check database load: Query execution plan

**Resolution**:
- If artifact API slow: Investigate, optimize queries or add index
- If network issue: Check regional routing, may need CDN tuning
- If code issue: Optimize Next.js API route, cache better

## RB-4: Incident Response Playbook

**On alert**:
1. Create incident channel: #incident-YYYY-MM-DD-HH-MM
2. Invite: On-call engineer, SRE, Governance lead
3. Start timeline: List events in chronological order

**During incident**:
1. Updates every 5 minutes (chat)
2. Investigation in parallel (don't wait to be 100% sure)
3. Communication: Keep stakeholders posted

**Post-incident**:
1. Write blameless postmortem (within 24h)
2. Root cause: Why did this happen?
3. Follow-up actions: How to prevent recurrence?
4. Action items with owners + deadlines

**Escalation matrix**:
- Severity 1 (prod down): Page on-call engineer + SRE + leadership
- Severity 2 (degraded): Page on-call engineer
- Severity 3 (warning): Alert but no page
