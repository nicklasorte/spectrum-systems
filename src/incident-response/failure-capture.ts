import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Failure Capture
 * When a pipeline run fails, capture artifacts for postmortem + learning
 */

export interface FailureCapture {
  failure_id: string;
  run_id: string;
  mvp_name: string;
  failure_reason: string;
  captured_at: string;
  lineage_trace: string[];
  sli_snapshot: Record<string, number>;
  control_signals: any[];
  recommended_action: string;
}

export class FailureCaptureEngine {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async captureFailure(
    runId: string,
    mvpName: string,
    failureReason: string,
    lineageTrace: string[],
    sliSnapshot: Record<string, number>,
    controlSignals: any[]
  ): Promise<FailureCapture> {
    const failureId = uuidv4();

    // Determine recommended action based on failure type
    let recommendedAction = "manual_review";
    if (failureReason.includes("eval_pass_rate")) {
      recommendedAction = "rerun_evals";
    } else if (failureReason.includes("cost")) {
      recommendedAction = "optimize_prompts";
    } else if (failureReason.includes("schema")) {
      recommendedAction = "fix_output_format";
    }

    const capture: FailureCapture = {
      failure_id: failureId,
      run_id: runId,
      mvp_name: mvpName,
      failure_reason: failureReason,
      captured_at: new Date().toISOString(),
      lineage_trace: lineageTrace,
      sli_snapshot: sliSnapshot,
      control_signals: controlSignals,
      recommended_action: recommendedAction,
    };

    // Store failure artifact
    await this.pool.query(
      `INSERT INTO failure_captures (failure_id, run_id, mvp_name, failure_reason, lineage_trace, sli_snapshot, recommended_action)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        failureId,
        runId,
        mvpName,
        failureReason,
        JSON.stringify(lineageTrace),
        JSON.stringify(sliSnapshot),
        recommendedAction,
      ]
    );

    return capture;
  }

  async getFrequentFailures(limit: number = 10): Promise<any[]> {
    const result = await this.pool.query(
      `SELECT failure_reason, COUNT(*) as count, MAX(captured_at) as latest
       FROM failure_captures
       WHERE captured_at > NOW() - INTERVAL '7 days'
       GROUP BY failure_reason
       ORDER BY count DESC
       LIMIT $1`,
      [limit]
    );
    return result.rows;
  }

  async createPostmortemTemplate(failure: FailureCapture): Promise<string> {
    return `
# Postmortem: ${failure.mvp_name} Failure

**Date**: ${failure.captured_at}
**Failure ID**: ${failure.failure_id}
**Run ID**: ${failure.run_id}

## Summary
${failure.failure_reason}

## Timeline
- Failed at: ${failure.captured_at}
- Failed MVP: ${failure.mvp_name}
- Affected lineage: ${failure.lineage_trace.join(" → ")}

## SLI Snapshot at Failure
${Object.entries(failure.sli_snapshot)
  .map(([k, v]) => `- ${k}: ${v}`)
  .join("\n")}

## Control Signals
${failure.control_signals.map((s) => `- ${s.signal_type}: ${s.context}`).join("\n")}

## Root Cause
(To be determined)

## Action Items
1. ${failure.recommended_action}
2. (Add preventive measure)
3. (Add test case)

## Learning
(What did we learn? How do we prevent recurrence?)
    `;
  }
}
