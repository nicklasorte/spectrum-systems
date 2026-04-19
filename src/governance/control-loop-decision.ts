import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Control Loop Decision
 * GOVERNANCE: All decisions are artifacts, never direct enforcement
 * Separation of authority: AI generates eval_summary, control loop generates decision_artifact
 * Only CI/orchestration layer can execute enforcement actions
 */

export interface ControlLoopDecision {
  artifact_kind: "control_loop_decision";
  artifact_id: string;
  target_artifact_id: string;
  eval_summary_id: string;
  policy_version: string;
  decision: "allow" | "warn" | "freeze" | "block";
  reason_codes: string[];
  trace_id: string;
  created_at: string;
  created_by: "system" | "human"; // who made the decision
}

export interface EnforcementAction {
  artifact_kind: "enforcement_action";
  artifact_id: string;
  control_decision_id: string;
  action_type: "promote" | "freeze_pipeline" | "rollback" | "escalate";
  action_details: string;
  status: "pending" | "approved" | "executed" | "failed";
  approver?: string; // human who approved
  executed_at?: string;
  trace_id: string;
  created_at: string;
}

export class ControlLoopEvaluator {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async initialize(): Promise<void> {
    // Control loop decisions (immutable, auditable)
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS control_loop_decisions (
        decision_id UUID PRIMARY KEY,
        target_artifact_id UUID NOT NULL,
        eval_summary_id UUID,
        policy_version VARCHAR(255),
        decision VARCHAR(50) NOT NULL,
        reason_codes JSONB,
        trace_id UUID,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by VARCHAR(50),
        INDEX idx_target_artifact (target_artifact_id),
        INDEX idx_decision (decision),
        INDEX idx_created_at (created_at)
      )
    `);

    // Enforcement actions (what CI/orchestration must execute)
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS enforcement_actions (
        action_id UUID PRIMARY KEY,
        control_decision_id UUID NOT NULL,
        action_type VARCHAR(50) NOT NULL,
        action_details TEXT,
        status VARCHAR(50) DEFAULT 'pending',
        approver VARCHAR(255),
        executed_at TIMESTAMP,
        trace_id UUID,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_control_decision (control_decision_id),
        INDEX idx_status (status),
        INDEX idx_action_type (action_type)
      )
    `);
  }

  /**
   * Evaluate artifact against SLOs and policies
   * Returns decision artifact (never executes directly)
   * Caller (CI/orchestration) decides whether to execute
   */
  async evaluateArtifact(
    targetArtifactId: string,
    evalSummaryId: string,
    policyVersion: string,
    traceId: string
  ): Promise<ControlLoopDecision> {
    // Fetch eval summary (read-only)
    const evalResult = await this.pool.query(
      `SELECT * FROM artifacts WHERE artifact_id = $1`,
      [evalSummaryId]
    );

    const evalData = evalResult.rows[0];

    // Fetch active policy (read-only)
    const policyResult = await this.pool.query(
      `SELECT * FROM artifacts WHERE artifact_kind = 'policy_definition' AND payload->>'policy_version' = $1`,
      [policyVersion]
    );

    if (policyResult.rows.length === 0) {
      // Policy not found or not active — block by default (fail-closed)
      const decision: ControlLoopDecision = {
        artifact_kind: "control_loop_decision",
        artifact_id: uuidv4(),
        target_artifact_id: targetArtifactId,
        eval_summary_id: evalSummaryId,
        policy_version: policyVersion,
        decision: "block",
        reason_codes: ["policy_not_found"],
        trace_id: traceId,
        created_at: new Date().toISOString(),
        created_by: "system",
      };

      // Store decision (read-only from here on)
      await this.recordDecision(decision);
      return decision;
    }

    // Deterministic logic (no AI, no side effects)
    const decision = this.applyControlLogic(
      evalData,
      traceId,
      targetArtifactId,
      evalSummaryId,
      policyVersion
    );

    // Store decision artifact (immutable)
    await this.recordDecision(decision);

    return decision;
  }

  private applyControlLogic(
    evalData: any,
    traceId: string,
    targetArtifactId: string,
    evalSummaryId: string,
    policyVersion: string
  ): ControlLoopDecision {
    const reasonCodes: string[] = [];

    // Fail-closed defaults
    if (!evalData || !evalData.artifact_id) {
      return {
        artifact_kind: "control_loop_decision",
        artifact_id: uuidv4(),
        target_artifact_id: targetArtifactId,
        eval_summary_id: evalSummaryId,
        policy_version: policyVersion,
        decision: "block",
        reason_codes: ["missing_eval_summary"],
        trace_id: traceId,
        created_at: new Date().toISOString(),
        created_by: "system",
      };
    }

    // Simple pass/fail logic based on eval_summary
    const evalPayload = evalData.payload || {};
    const passed = evalPayload.status === "pass";

    if (!passed) {
      reasonCodes.push("eval_failed");
      return {
        artifact_kind: "control_loop_decision",
        artifact_id: uuidv4(),
        target_artifact_id: targetArtifactId,
        eval_summary_id: evalSummaryId,
        policy_version: policyVersion,
        decision: "block",
        reason_codes: reasonCodes,
        trace_id: traceId,
        created_at: new Date().toISOString(),
        created_by: "system",
      };
    }

    // Default to allow (eval passed)
    return {
      artifact_kind: "control_loop_decision",
      artifact_id: uuidv4(),
      target_artifact_id: targetArtifactId,
      eval_summary_id: evalSummaryId,
      policy_version: policyVersion,
      decision: "allow",
      reason_codes: ["eval_passed"],
      trace_id: traceId,
      created_at: new Date().toISOString(),
      created_by: "system",
    };
  }

  private async recordDecision(decision: ControlLoopDecision): Promise<void> {
    await this.pool.query(
      `INSERT INTO control_loop_decisions (decision_id, target_artifact_id, eval_summary_id, policy_version, decision, reason_codes, trace_id, created_by)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
      [
        uuidv4(),
        decision.target_artifact_id,
        decision.eval_summary_id,
        decision.policy_version,
        decision.decision,
        JSON.stringify(decision.reason_codes),
        decision.trace_id,
        decision.created_by,
      ]
    );
  }

  /**
   * Create enforcement action (orchestration/CI must execute)
   * Decision artifact → enforcement action artifact → (human/CI execution)
   * Never execute directly from here
   */
  async createEnforcementAction(
    controlDecisionId: string,
    actionType: "promote" | "freeze_pipeline" | "rollback" | "escalate",
    actionDetails: string,
    traceId: string
  ): Promise<EnforcementAction> {
    const action: EnforcementAction = {
      artifact_kind: "enforcement_action",
      artifact_id: uuidv4(),
      control_decision_id: controlDecisionId,
      action_type: actionType,
      action_details: actionDetails,
      status: "pending", // waits for CI/human approval
      trace_id: traceId,
      created_at: new Date().toISOString(),
    };

    // Store action artifact
    await this.pool.query(
      `INSERT INTO enforcement_actions (action_id, control_decision_id, action_type, action_details, status, trace_id)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [
        action.artifact_id,
        controlDecisionId,
        actionType,
        actionDetails,
        action.status,
        traceId,
      ]
    );

    return action;
  }

  /**
   * Query pending enforcement actions (for CI/orchestration to execute)
   * CI/orchestration layer polls this and executes via GitHub Actions, etc.
   */
  async getPendingEnforcementActions(
    limit: number = 50
  ): Promise<EnforcementAction[]> {
    const result = await this.pool.query(
      `SELECT * FROM enforcement_actions WHERE status = 'pending' ORDER BY created_at ASC LIMIT $1`,
      [limit]
    );

    return result.rows.map((r) => ({
      artifact_kind: "enforcement_action" as const,
      artifact_id: r.action_id,
      control_decision_id: r.control_decision_id,
      action_type: r.action_type,
      action_details: r.action_details,
      status: r.status,
      approver: r.approver,
      executed_at: r.executed_at,
      trace_id: r.trace_id,
      created_at: r.created_at,
    }));
  }

  /**
   * Mark enforcement action as approved by human/CI
   * (Does not execute; just marks as approved for external orchestration)
   */
  async approveEnforcementAction(
    actionId: string,
    approver: string
  ): Promise<void> {
    await this.pool.query(
      `UPDATE enforcement_actions SET approver = $1, status = 'approved' WHERE action_id = $2`,
      [approver, actionId]
    );
  }

  /**
   * CI/orchestration calls this after successfully executing action
   * (e.g., after GitHub Actions runs and completes promotion)
   */
  async markEnforcementActionExecuted(actionId: string): Promise<void> {
    await this.pool.query(
      `UPDATE enforcement_actions SET status = 'executed', executed_at = NOW() WHERE action_id = $1`,
      [actionId]
    );
  }
}
