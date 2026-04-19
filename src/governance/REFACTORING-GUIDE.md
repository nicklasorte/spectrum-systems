# Governance Refactoring Guide

## Issue: PROTECTED_AUTHORITY_VIOLATION

Code was making autonomous decisions and executing enforcement without explicit governance gates.

## Root Cause

Any component that directly:
1. Makes policy decisions
2. Executes enforcement actions
3. Modifies system state based on evaluations
4. Bypasses audit trails

...violates separation of authority.

## Fix Pattern

### Before (Violations)

```typescript
class PolicyEngine {
  async deployPolicy() {
    // ❌ VIOLATION: Direct execution from logic component
    await this.s3.putObject(...); // Autonomously deploys
  }

  async enforceOverride() {
    // ❌ VIOLATION: State mutation without explicit artifact
    this.state.overrides.push(...); // No control decision
  }
}
```

### After (Fixed)

```typescript
// 1. Create decision artifact
const decision = await evaluator.evaluateArtifact(
  targetId,
  evalSummaryId,
  policyVersion,
  traceId
);

// 2. Create enforcement action artifact (pending)
const action = await evaluator.createEnforcementAction(
  decision.artifact_id,
  "promote",
  "Deploy policy after evaluation",
  traceId
);

// 3. CI/orchestration polls and executes
const pending = await evaluator.getPendingEnforcementActions();
// pending[0] has status="pending"
// CI approves → orchestration executes → marks executed
```

## Checklist for Refactoring

For each component that has enforcement logic:

- [ ] Extract evaluation logic (read-only, deterministic)
- [ ] Create decision artifact via `ControlLoopEvaluator.evaluateArtifact()`
- [ ] Create enforcement action via `ControlLoopEvaluator.createEnforcementAction()`
- [ ] Set status to "pending" (never "executed")
- [ ] Remove all direct state mutations
- [ ] Remove all direct AWS/S3/API calls from logic
- [ ] Add test: verify decision artifact is immutable
- [ ] Add test: verify enforcement action awaits approval

## Example: PolicyDeployment Refactoring

### Before

```typescript
class PolicyEngine {
  async deployPolicy(policyId: string) {
    const policy = await this.load(policyId);
    // Autonomously deploy!
    await this.s3.putObject({
      Key: `policies/${policyId}`,
      Body: JSON.stringify(policy),
    });
  }
}
```

### After

```typescript
class PolicyEvaluator {
  // 1. Evaluate (read-only)
  async evaluate(policyId: string) {
    const decision = await this.controlLoop.evaluateArtifact(
      policyId,
      evalSummaryId,
      "1.0",
      traceId
    );
    // Returns: "allow" (recommends deploy) or "block" (recommends reject)
    return decision; // ARTIFACT, never executed
  }
}

// 2. CI/orchestration layer handles execution
const decision = await evaluator.evaluate(policyId);
if (decision.decision === "allow") {
  const action = await evaluator.createEnforcementAction(
    decision.artifact_id,
    "promote",
    `Deploy policy ${policyId}`,
    traceId
  );
  // CI sees action with status="pending"
  // CI approves, orchestration executes, CI marks executed
}
```

## Authority Boundaries

### AI/Logic Components (Read-Only)
- Evaluate artifacts
- Return decision artifacts (never execute)
- All outputs are immutable artifacts

### ControlLoopEvaluator (Decision Artifact Generator)
- Reads eval_summary and policy
- Generates control_loop_decision artifact
- Generates enforcement_action artifact (status=pending)
- No execution, no side effects

### CI/Orchestration Layer (Execution)
- Polls `getPendingEnforcementActions()`
- Decides approval (human or automated)
- Executes via GitHub Actions, webhooks, etc.
- Marks `markEnforcementActionExecuted()` when done

### Audit/Governance
- Every decision is an artifact (queryable, traceable)
- Every action requires explicit approval
- Every execution is recorded with timestamp and approver
- Full chain: decision → action → approval → execution → audit

## Testing

Every refactored component should have tests for:

1. **Decision artifact is generated** (not executed)
2. **Enforcement action has status="pending"** (awaits approval)
3. **No direct state mutations** in logic layer
4. **Audit trail is complete** (all artifacts are recorded)
5. **Fail-closed on missing policy** (block, not allow)
