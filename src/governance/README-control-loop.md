# Control Loop Decision Architecture (Strict Governance)

**GOVERNANCE RULE: AI code never creates enforcement actions**

## What This Code Does

1. Reads eval_summary (artifact)
2. Reads policy_definition (artifact)
3. Applies deterministic logic (no side effects)
4. Stores decision artifact
5. **STOPS** — never creates enforcement_action

## What CI/Orchestration Does

1. Polls `getDecisions()` or `getBlockingDecisions()`
2. Creates enforcement_action artifacts (outside this repo)
3. Executes enforcement via GitHub Actions
4. Records execution status

## Architecture

```
Artifact Storage (PostgreSQL)
        ↓
eval_summary + policy_definitions
        ↓
ControlLoopEvaluator (TypeScript)
  - reads (no side effects)
  - computes (deterministic)
  - stores decision
  - STOPS (no enforcement_action creation)
        ↓
Queries: getDecisions(), getBlockingDecisions()
        ↓
CI/Orchestration (GitHub Actions, external)
  - creates enforcement_action (not in this code)
  - executes (promotes, freezes, rollbacks)
  - records result
```

## Decision Flow

1. **AI evaluates** (e.g., MVP-8 generates paper)
2. **Eval harness tests** (e.g., MVP-9 produces eval_summary)
3. **Control loop reads** eval_summary + policy artifacts
4. **Control loop computes** decision (deterministic, no AI)
5. **Control loop stores** control_loop_decision artifact
6. **Control loop STOPS** (no enforcement_action)
7. **CI queries** getDecisions() / getBlockingDecisions()
8. **CI creates** enforcement_action (outside this code)
9. **CI executes** (GitHub Actions, webhooks)
10. **CI records** result

## Key Rules

- **No side effects in evaluator**: Only reads, writes decision artifact only
- **Decision is separate from execution**: Generating a decision != executing it
- **No enforcement action creation in code**: CI/orchestration owns all enforcement
- **All decisions are artifacts**: Auditable, traceable, queryable
- **CI/orchestration owns execution**: System can recommend, cannot force

## Tables

### control_loop_decisions
- `decision_id`: UUID primary key
- `target_artifact_id`: artifact being evaluated
- `eval_summary_id`: evaluation result artifact
- `policy_version`: policy version used
- `decision`: "allow", "warn", "freeze", "block"
- `reason_codes`: JSON array of decision rationale
- `trace_id`: trace context for correlation
- `created_at`: decision timestamp

## Code Does Not Have

- ❌ `createEnforcementAction()` method
- ❌ `approveEnforcementAction()` method
- ❌ `markEnforcementActionExecuted()` method
- ❌ enforcement_actions table

All enforcement is external (CI/orchestration)
