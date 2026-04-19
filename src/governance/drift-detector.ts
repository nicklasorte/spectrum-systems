import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Drift Detector
 * Monitors six entropy vectors: decision divergence, metric distribution shifts,
 * exception accumulation, trace loss, eval blind spots, and hidden logic creep
 */

export interface DriftSignal {
  artifact_kind: "drift_signal";
  artifact_id: string;
  drift_type: "decision_divergence" | "metric_distribution" | "exception_accumulation" | "trace_loss";
  sli_name?: string;
  baseline_value: number;
  current_value: number;
  threshold: number;
  triggered_at: string;
  recommendations: string[];
  resolved_at?: string;
}

export class DriftDetector {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async initialize(): Promise<void> {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS drift_signals (
        signal_id UUID PRIMARY KEY,
        drift_type VARCHAR(255) NOT NULL,
        sli_name VARCHAR(255),
        baseline_value NUMERIC,
        current_value NUMERIC,
        threshold NUMERIC,
        triggered_at TIMESTAMP NOT NULL,
        resolved_at TIMESTAMP,
        recommendations JSONB,
        status VARCHAR(50) DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_drift_type (drift_type),
        INDEX idx_status (status),
        INDEX idx_triggered_at (triggered_at)
      )
    `);
  }

  async detectDecisionDivergence(artifactType: string): Promise<DriftSignal | null> {
    const result = await this.pool.query(
      `SELECT COUNT(DISTINCT outcome) as outcome_count
       FROM audit_entries
       WHERE artifact_id IN (
         SELECT artifact_id FROM artifacts WHERE artifact_kind = $1
       )
       AND created_at > NOW() - INTERVAL '24 hours'`,
      [artifactType]
    );

    const outcomeCount = result.rows[0]?.outcome_count || 0;
    const threshold = 2;

    if (outcomeCount > threshold) {
      const signal: DriftSignal = {
        artifact_kind: "drift_signal",
        artifact_id: uuidv4(),
        drift_type: "decision_divergence",
        baseline_value: 1,
        current_value: outcomeCount,
        threshold,
        triggered_at: new Date().toISOString(),
        recommendations: [
          "Review outcome logic for inconsistency",
          "Check if policy changed recently",
          "Audit reviewer behavior for calibration drift",
        ],
      };

      await this.recordSignal(signal);
      return signal;
    }

    return null;
  }

  async detectMetricDistributionShift(sliName: string): Promise<DriftSignal | null> {
    const result = await this.pool.query(
      `SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) as current_median
       FROM sli_measurements
       WHERE sli_name = $1 AND timestamp > NOW() - INTERVAL '24 hours'`,
      [sliName]
    );

    const baselineResult = await this.pool.query(
      `SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) as baseline_median
       FROM sli_measurements
       WHERE sli_name = $1 AND timestamp > NOW() - INTERVAL '30 days' AND timestamp < NOW() - INTERVAL '24 hours'`,
      [sliName]
    );

    const currentMedian = result.rows[0]?.current_median || 0;
    const baselineMedian = baselineResult.rows[0]?.baseline_median || currentMedian;
    const threshold = 10;

    const percentageShift = baselineMedian > 0 ? Math.abs((currentMedian - baselineMedian) / baselineMedian) * 100 : 0;

    if (percentageShift > threshold) {
      const signal: DriftSignal = {
        artifact_kind: "drift_signal",
        artifact_id: uuidv4(),
        drift_type: "metric_distribution",
        sli_name,
        baseline_value: baselineMedian,
        current_value: currentMedian,
        threshold,
        triggered_at: new Date().toISOString(),
        recommendations: [
          `SLI "${sliName}" shifted ${percentageShift.toFixed(1)}% from baseline`,
          "Investigate upstream changes (model, policy, context)",
          "Consider freeze if shift is toward worse performance",
        ],
      };

      await this.recordSignal(signal);
      return signal;
    }

    return null;
  }

  async detectExceptionAccumulation(): Promise<DriftSignal | null> {
    const result = await this.pool.query(
      `SELECT COUNT(*) as exception_count FROM exception_records WHERE status = 'active' AND expiry_date > NOW()`
    );

    const exceptionCount = result.rows[0]?.exception_count || 0;
    const threshold = 10;

    if (exceptionCount > threshold) {
      const signal: DriftSignal = {
        artifact_kind: "drift_signal",
        artifact_id: uuidv4(),
        drift_type: "exception_accumulation",
        baseline_value: threshold,
        current_value: exceptionCount,
        threshold,
        triggered_at: new Date().toISOString(),
        recommendations: [
          `${exceptionCount} active exceptions exceed threshold of ${threshold}`,
          "Convert frequent exceptions into policy or eval rules",
          "Retire unused exceptions",
        ],
      };

      await this.recordSignal(signal);
      return signal;
    }

    return null;
  }

  async detectTraceLoss(): Promise<DriftSignal | null> {
    const result = await this.pool.query(
      `SELECT
        COUNT(*) as total_runs,
        COUNT(CASE WHEN trace_id IS NULL THEN 1 END) as missing_trace
       FROM artifacts
       WHERE created_at > NOW() - INTERVAL '24 hours'`
    );

    const totalRuns = result.rows[0]?.total_runs || 0;
    const missingTrace = result.rows[0]?.missing_trace || 0;
    const tracePercentage = totalRuns > 0 ? (1 - missingTrace / totalRuns) * 100 : 0;
    const threshold = 95;

    if (tracePercentage < threshold) {
      const signal: DriftSignal = {
        artifact_kind: "drift_signal",
        artifact_id: uuidv4(),
        drift_type: "trace_loss",
        baseline_value: threshold,
        current_value: tracePercentage,
        threshold,
        triggered_at: new Date().toISOString(),
        recommendations: [
          `Trace coverage ${tracePercentage.toFixed(1)}% below target ${threshold}%`,
          "Check trace context propagation in MVPs",
          "Audit artifact creation for missing trace_id",
        ],
      };

      await this.recordSignal(signal);
      return signal;
    }

    return null;
  }

  private async recordSignal(signal: DriftSignal): Promise<void> {
    await this.pool.query(
      `INSERT INTO drift_signals (signal_id, drift_type, sli_name, baseline_value, current_value, threshold, triggered_at, recommendations, status)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
      [
        signal.artifact_id,
        signal.drift_type,
        signal.sli_name,
        signal.baseline_value,
        signal.current_value,
        signal.threshold,
        signal.triggered_at,
        JSON.stringify(signal.recommendations),
        "active",
      ]
    );
  }

  async getActiveDriftSignals(limit: number = 50): Promise<DriftSignal[]> {
    const result = await this.pool.query(
      `SELECT * FROM drift_signals
       WHERE status = 'active' AND triggered_at > NOW() - INTERVAL '7 days'
       ORDER BY triggered_at DESC LIMIT $1`,
      [limit]
    );

    return result.rows.map((row) => ({
      artifact_kind: "drift_signal" as const,
      artifact_id: row.signal_id,
      drift_type: row.drift_type,
      sli_name: row.sli_name,
      baseline_value: row.baseline_value,
      current_value: row.current_value,
      threshold: row.threshold,
      triggered_at: row.triggered_at,
      recommendations: JSON.parse(row.recommendations || "[]"),
      resolved_at: row.resolved_at,
    }));
  }

  async markDriftSignalResolved(signalId: string): Promise<void> {
    await this.pool.query(
      `UPDATE drift_signals SET status = 'resolved', resolved_at = NOW() WHERE signal_id = $1`,
      [signalId]
    );
  }
}
