# Control Loop (Strict Governance Version)

**GOVERNANCE RULE: AI code never creates enforcement actions**

## What This Code Does

1. Reads eval_summary (artifact)
2. Reads policy_definition (artifact)
3. Applies deterministic logic (no side effects)
4. Stores decision artifact
5. STOPS

## What CI/Orchestration Does

1. Polls control_loop_decisions
2. Creates enforcement_action artifacts (outside this repo)
3. Executes enforcement via GitHub Actions
4. Records execution status

## Architecture

```
Artifact Storage (PostgreSQL)
       ↓
ControlLoopEvaluator (TypeScript)
 • reads artifacts
 • computes decisions (deterministic, no AI)
 • writes decision artifacts
 • STOPS (no enforcement_action creation)
       ↓
Queries: getDecisions(), getBlockingDecisions()
       ↓
CI/Orchestration (GitHub Actions)
 • creates enforcement_action (not in this code)
 • executes (promotes, freezes, etc.)
 • records result
```

## Key Files

- **control-loop-decision.ts**: ControlLoopEvaluator (reads, computes, writes decisions only)
- **CI_ORCHESTRATION_LAYER.md**: How external systems create and execute enforcement
- **tests/governance/**: Verify no enforcement action creation in code

## No Enforcement in Code

This codebase:
- ✅ Reads artifacts
- ✅ Computes decisions
- ✅ Stores decisions
- ❌ Never creates enforcement_action
- ❌ Never executes actions
- ❌ Never calls external systems

External (CI):
- ✅ Polls decisions
- ✅ Creates enforcement_action
- ✅ Executes
- ✅ Records result

## Methods

### evaluateArtifact(targetArtifactId, evalSummaryId, policyVersion, traceId)

Evaluate artifact against eval_summary and policy.

Returns: `ControlLoopDecision` (allow | warn | freeze | block)

Does NOT create enforcement_action.

### getDecisions(targetArtifactId?, limit)

Query stored decisions (for CI to read).

Returns: `ControlLoopDecision[]`

### getBlockingDecisions(limit)

Query block/freeze decisions (for CI to prioritize).

Returns: `ControlLoopDecision[]` with decision in (block, freeze)

## No These Methods

- ❌ `createEnforcementAction()` — CI's job
- ❌ `approveEnforcementAction()` — CI's job
- ❌ `markEnforcementActionExecuted()` — CI's job
