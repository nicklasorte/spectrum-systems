# CI/Orchestration Layer (GitHub Actions)

This is where enforcement actions are created and executed.

The control loop (TypeScript code) only:
- Reads eval_summary and policy artifacts
- Computes decision
- Stores decision artifact
- STOPS

CI/orchestration (GitHub Actions, external) does:
1. Poll `evaluator.getDecisions()`
2. For each "block" decision: create enforcement_action (stop/rollback)
3. For each "warn" decision: create enforcement_action (alert)
4. For each "allow" decision: create enforcement_action (promote)
5. Execute enforcement_action via GitHub Actions
6. Record result back to database

## Example GitHub Actions Workflow

```yaml
name: Enforce Control Loop Decisions

on: [workflow_dispatch]

jobs:
  enforce:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Query control loop decisions
        run: |
          # Call API to get pending decisions
          curl -X GET http://localhost:3000/api/decisions/pending \
            -o decisions.json
      
      - name: Execute enforcement
        run: |
          # For each block decision: stop pipeline
          # For each allow decision: promote artifact
          # (enforcement_action artifacts created here, not in code)
          python scripts/enforce_decisions.py
      
      - name: Record execution
        run: |
          # Update control_loop_decisions with execution status
          # Artifact store records that action was taken
```

## Key Rule

**Enforcement actions are created by CI/orchestration, never by application code.**

Application code:

- Reads artifacts
- Computes decisions
- Writes decision artifacts
- STOPS

CI/orchestration:

- Reads decision artifacts
- Creates enforcement_action artifacts (outside this repo)
- Executes (GitHub Actions, K8s, etc.)
- Records result
