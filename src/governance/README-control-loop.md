# Control Loop Decision Architecture

**GOVERNANCE: Separation of Authority**

The control loop is fully deterministic and reads artifacts only. It never executes enforcement.

## Decision Flow

1. **AI evaluates** (e.g., MVP-8 generates paper)
2. **Eval harness tests** (e.g., MVP-9 produces eval_summary)
3. **Control loop reads** eval_summary + policy artifacts (no side effects, no API calls)
4. **Control loop generates** control_loop_decision artifact (e.g., "allow", "warn", "block")
5. **Control decision artifact stored** (immutable, auditable, traced)
6. **Orchestration queries** getPendingEnforcementActions()
7. **Orchestration executes** (GitHub Actions, human approval, etc.)
8. **Orchestration records** markEnforcementActionExecuted()

## Key Rules

- **No side effects in evaluator**: Only reads, never writes state (except decision artifact)
- **Decision is separate from execution**: Generating a decision != executing it
- **Every enforcement action waits for approval**: Status flow: pending → approved → executed
- **All decisions are artifacts**: Auditable, traceable, queryable
- **CI/orchestration owns execution**: System can recommend, but cannot force

## Example

```
Paper artifact → eval_summary "pass" → control_loop_decision "allow"
→ enforcement_action "promote" (pending)
→ CI polls → sees "promote" pending
→ CI approves → orchestration promotes
→ CI marks executed
```

## Tables

### control_loop_decisions
- `decision_id`: UUID primary key
- `target_artifact_id`: artifact being evaluated
- `eval_summary_id`: evaluation result artifact
- `policy_version`: policy version used
- `decision`: "allow", "warn", "freeze", "block"
- `reason_codes`: JSON array of decision rationale
- `trace_id`: trace context for correlation
- `created_by`: "system" or "human"

### enforcement_actions
- `action_id`: UUID primary key
- `control_decision_id`: decision that triggered action
- `action_type`: "promote", "freeze_pipeline", "rollback", "escalate"
- `status`: "pending" → "approved" → "executed"
- `approver`: who approved execution
- `executed_at`: when orchestration completed action
