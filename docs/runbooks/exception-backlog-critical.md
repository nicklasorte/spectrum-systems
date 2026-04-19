# Exception Backlog Critical Runbook

## When exception_backlog status = critical (> 10 active)

**Automated action**: FREEZE_PIPELINE immediately

**Manual action (engineering lead)**:

1. **Triage (15 min)**
   - List all active exceptions: `SELECT exception_id, reason, expiry_date FROM exception_artifacts WHERE status='active' ORDER BY expiry_date ASC`
   - Categorize: convert_to_policy (60%) | retire (30%) | extend (10%)

2. **Convert to Policy (30 min per exception)**
   - For each "should be a rule" exception:
     - Write policy definition in `src/governance/policies/`
     - Add test cases
     - Deploy with 10% canary rollout
     - Mark exception as `converted_to_policy`

3. **Retire (10 min per exception)**
   - For each "no longer needed" exception:
     - Verify expiry date has passed
     - Mark as `retired`

4. **Extend (5 min per exception)**
   - For each "needs more time" exception:
     - Add 30 days to expiry_date
     - Document reason in notes
     - Note: can only extend once

5. **Unfreeze**
   - Once backlog < 5: unfreeze pipeline
   - Verify in next run: `SELECT COUNT(*) FROM exception_artifacts WHERE status='active'`

**Prevention**:
- Review exception backlog weekly
- Convert high-frequency exceptions immediately
- Retire expired exceptions automatically (cleanup job)
