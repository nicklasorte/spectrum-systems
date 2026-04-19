# Policy Incident & Rollback Runbook

## When policy has > 5 incidents in 24h

**Automated action**: FREEZE_PIPELINE, page team lead

**Manual action (engineering lead)**:

1. **Assess (10 min)**
   - Incidents: `SELECT COUNT(*) FROM escalation_events WHERE policy_id = $1 AND created_at > NOW() - INTERVAL '24 hours'`
   - Incident types: classification, pattern analysis
   - User impact: how many artifacts affected

2. **Decide (5 min)**
   - If incidents are noise (false alarms): dismiss
   - If real issue: initiate rollback

3. **Rollback (5 min)**
   - Policy auto-rollback trigger fires (if enabled)
   - If manual: `UPDATE policy_definitions SET status='deprecated', rollout_percentage=0 WHERE policy_id=$1`
   - Mark previous version as active: `UPDATE policy_definitions SET status='active', rollout_percentage=100 WHERE policy_id=$2`

4. **Post-Incident (next morning)**
   - Create postmortem artifact with root cause
   - Link to policy definition
   - Document: what went wrong, how to prevent, action items
   - Assign owner for fix

5. **Redeployment**
   - Fix policy issue
   - Create new version (v3)
   - Deploy with 5% canary (lower than v2)
   - Increase gradually if no incidents

**Prevention**:
- Test policies in staging with diverse eval cases
- Canary rollout catches issues early
- Monitor incident trends per policy
