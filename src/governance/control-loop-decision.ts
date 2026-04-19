import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Control Loop Decision (STRICT GOVERNANCE)
 *
 * GOVERNANCE RULE: AI code never creates enforcement actions
 *
 * This evaluator:
 * - Reads eval_summary and policy artifacts (no side effects)
 * - Applies deterministic logic
 * - Returns decision (no creation of enforcement_action)
 *
 * CI/orchestration layer:
 * - Queries control_loop_decisions
 * - Decides what enforcement action to take
 * - Creates enforcement_action artifacts (external to this code)
 * - Executes via GitHub Actions
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
  created_by: "system";
}

export class ControlLoopEvaluator {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async initialize(): Promise<void> {
    // Control loop decisions (immutable, auditable)
    // NO enforcement_actions table — that's CI's job
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
        INDEX idx_target_artifact (target_artifact_id),
        INDEX idx_decision (decision),
        INDEX idx_created_at (created_at)
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

    // Check eval status (deterministic logic, no side effects)
    const evalPayload = evalData.payload || {};
    const status = evalPayload.status || "unknown";

    if (status === "block") {
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

    if (status === "warn") {
      reasonCodes.push("eval_warning");
      return {
        artifact_kind: "control_loop_decision",
        artifact_id: uuidv4(),
        target_artifact_id: targetArtifactId,
        eval_summary_id: evalSummaryId,
        policy_version: policyVersion,
        decision: "warn",
        reason_codes: reasonCodes,
        trace_id: traceId,
        created_at: new Date().toISOString(),
        created_by: "system",
      };
    }

    // Default to allow (eval passed)
    reasonCodes.push("eval_passed");
    return {
      artifact_kind: "control_loop_decision",
      artifact_id: uuidv4(),
      target_artifact_id: targetArtifactId,
      eval_summary_id: evalSummaryId,
      policy_version: policyVersion,
      decision: "allow",
      reason_codes: reasonCodes,
      trace_id: traceId,
      created_at: new Date().toISOString(),
      created_by: "system",
    };
  }

  private async recordDecision(decision: ControlLoopDecision): Promise<void> {
    await this.pool.query(
      `INSERT INTO control_loop_decisions (decision_id, target_artifact_id, eval_summary_id, policy_version, decision, reason_codes, trace_id)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        uuidv4(),
        decision.target_artifact_id,
        decision.eval_summary_id,
        decision.policy_version,
        decision.decision,
        JSON.stringify(decision.reason_codes),
        decision.trace_id,
      ]
    );
  }

  /**
   * Query decisions (for CI/orchestration to read)
   * CI uses these to decide what enforcement actions to take
   */
  async getDecisions(
    targetArtifactId?: string,
    limit: number = 50
  ): Promise<ControlLoopDecision[]> {
    let query = `SELECT * FROM control_loop_decisions`;
    const params: any[] = [];

    if (targetArtifactId) {
      query += ` WHERE target_artifact_id = $1`;
      params.push(targetArtifactId);
    }

    query += ` ORDER BY created_at DESC LIMIT $${params.length + 1}`;
    params.push(limit);

    const result = await this.pool.query(query, params);

    return result.rows.map((r) => ({
      artifact_kind: "control_loop_decision" as const,
      artifact_id: r.decision_id,
      target_artifact_id: r.target_artifact_id,
      eval_summary_id: r.eval_summary_id,
      policy_version: r.policy_version,
      decision: r.decision,
      reason_codes: JSON.parse(r.reason_codes || "[]"),
      trace_id: r.trace_id,
      created_at: r.created_at,
      created_by: "system",
    }));
  }

  /**
   * Query block/warn decisions (for CI to prioritize)
   */
  async getBlockingDecisions(limit: number = 50): Promise<ControlLoopDecision[]> {
    const result = await this.pool.query(
      `SELECT * FROM control_loop_decisions
       WHERE decision IN ('block', 'freeze')
       ORDER BY created_at DESC LIMIT $1`,
      [limit]
    );

    return result.rows.map((r) => ({
      artifact_kind: "control_loop_decision" as const,
      artifact_id: r.decision_id,
      target_artifact_id: r.target_artifact_id,
      eval_summary_id: r.eval_summary_id,
      policy_version: r.policy_version,
      decision: r.decision,
      reason_codes: JSON.parse(r.reason_codes || "[]"),
      trace_id: r.trace_id,
      created_at: r.created_at,
      created_by: "system",
    }));
  }
}
