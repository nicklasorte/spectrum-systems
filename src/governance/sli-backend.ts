import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";
import type { SLIMeasurement, SLODefinition, BurnRateAlert } from "./sli-types";

/**
 * SLI Backend: Time-series storage and queries
 * Tracks all SLI measurements for governance
 */

export class SLIBackend {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async initialize(): Promise<void> {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS sli_measurements (
        measurement_id UUID PRIMARY KEY,
        sli_name VARCHAR(255) NOT NULL,
        run_id VARCHAR(255),
        timestamp TIMESTAMP NOT NULL,
        value NUMERIC NOT NULL,
        dimensions JSONB,
        trace_id UUID,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_sli_name (sli_name),
        INDEX idx_timestamp (timestamp),
        INDEX idx_trace_id (trace_id)
      )
    `);

    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS slo_definitions (
        slo_id UUID PRIMARY KEY,
        slo_name VARCHAR(255) NOT NULL,
        sli_name VARCHAR(255) NOT NULL,
        target_value NUMERIC NOT NULL,
        window_days INT NOT NULL,
        error_budget_percentage NUMERIC NOT NULL,
        grace_period_minutes INT NOT NULL,
        owner VARCHAR(255),
        supersedes UUID,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status VARCHAR(50) DEFAULT 'active',
        INDEX idx_sli_name (sli_name),
        INDEX idx_status (status)
      )
    `);

    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS burn_rate_alerts (
        alert_id UUID PRIMARY KEY,
        slo_id UUID NOT NULL,
        sli_name VARCHAR(255) NOT NULL,
        current_burn_rate NUMERIC NOT NULL,
        threshold_burn_rate NUMERIC NOT NULL,
        alert_level VARCHAR(50) NOT NULL,
        triggered_at TIMESTAMP NOT NULL,
        window_hours INT NOT NULL,
        context TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_slo_id (slo_id),
        INDEX idx_alert_level (alert_level),
        INDEX idx_triggered_at (triggered_at)
      )
    `);

    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS slo_status (
        status_id UUID PRIMARY KEY,
        slo_id UUID NOT NULL,
        window_start TIMESTAMP NOT NULL,
        window_end TIMESTAMP NOT NULL,
        budget_consumed_percentage NUMERIC NOT NULL,
        budget_remaining_percentage NUMERIC NOT NULL,
        measurement_count INT NOT NULL,
        avg_value NUMERIC,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(slo_id, window_start),
        INDEX idx_slo_id (slo_id),
        INDEX idx_updated_at (updated_at)
      )
    `);
  }

  async recordMeasurement(
    sliName: string,
    value: number,
    runId: string,
    dimensions?: Record<string, string>,
    traceId?: string
  ): Promise<void> {
    await this.pool.query(
      `INSERT INTO sli_measurements (measurement_id, sli_name, run_id, timestamp, value, dimensions, trace_id)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        uuidv4(),
        sliName,
        runId,
        new Date(),
        value,
        dimensions ? JSON.stringify(dimensions) : null,
        traceId,
      ]
    );
  }

  async getSLODefinition(sloName: string): Promise<SLODefinition | null> {
    const result = await this.pool.query(
      `SELECT * FROM slo_definitions WHERE slo_name = $1 AND status = 'active' ORDER BY created_at DESC LIMIT 1`,
      [sloName]
    );
    return result.rows.length > 0 ? result.rows[0] : null;
  }

  async calculateBudgetBurn(
    sloId: string
  ): Promise<{ budget_consumed: number; budget_remaining: number }> {
    const result = await this.pool.query(
      `SELECT budget_consumed_percentage, budget_remaining_percentage
       FROM slo_status
       WHERE slo_id = $1
       ORDER BY updated_at DESC LIMIT 1`,
      [sloId]
    );

    if (result.rows.length > 0) {
      return {
        budget_consumed: result.rows[0].budget_consumed_percentage,
        budget_remaining: result.rows[0].budget_remaining_percentage,
      };
    }

    return { budget_consumed: 0, budget_remaining: 100 };
  }

  async getMeasurementTrend(
    sliName: string,
    windowHours: number
  ): Promise<number[]> {
    const result = await this.pool.query(
      `SELECT value FROM sli_measurements
       WHERE sli_name = $1 AND timestamp > NOW() - INTERVAL '1 hour' * $2
       ORDER BY timestamp ASC`,
      [sliName, windowHours]
    );

    return result.rows.map((r) => r.value);
  }

  async calculateBurnRate(
    sliName: string,
    windowHours: number = 24
  ): Promise<number> {
    const measurements = await this.getMeasurementTrend(sliName, windowHours);

    if (measurements.length < 2) return 0;

    const firstValue = measurements[0];
    const lastValue = measurements[measurements.length - 1];

    if (firstValue <= 0 || windowHours <= 0) return 0;

    const changePercentage = ((lastValue - firstValue) / firstValue) * 100;
    const daysElapsed = windowHours / 24;

    return changePercentage / daysElapsed;
  }

  async recordBurnRateAlert(
    sloId: string,
    sliName: string,
    currentBurnRate: number,
    thresholdBurnRate: number,
    alertLevel: "warn" | "freeze" | "block",
    windowHours: number,
    context: string
  ): Promise<void> {
    await this.pool.query(
      `INSERT INTO burn_rate_alerts (alert_id, slo_id, sli_name, current_burn_rate, threshold_burn_rate, alert_level, triggered_at, window_hours, context)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
      [
        uuidv4(),
        sloId,
        sliName,
        currentBurnRate,
        thresholdBurnRate,
        alertLevel,
        new Date(),
        windowHours,
        context,
      ]
    );
  }

  async getActiveAlerts(limit: number = 100): Promise<BurnRateAlert[]> {
    const result = await this.pool.query(
      `SELECT * FROM burn_rate_alerts
       WHERE triggered_at > NOW() - INTERVAL '7 days'
       ORDER BY triggered_at DESC
       LIMIT $1`,
      [limit]
    );

    return result.rows.map((r) => ({
      artifact_kind: "burn_rate_alert" as const,
      artifact_id: r.alert_id,
      slo_id: r.slo_id,
      sli_name: r.sli_name,
      current_burn_rate: r.current_burn_rate,
      threshold_burn_rate: r.threshold_burn_rate,
      alert_level: r.alert_level,
      triggered_at: r.triggered_at,
      window_hours: r.window_hours,
      context: r.context,
    }));
  }

  async updateSLOStatus(
    sloId: string,
    budgetConsumedPercentage: number,
    measurementCount: number,
    avgValue?: number
  ): Promise<void> {
    const windowStart = new Date();
    windowStart.setDate(windowStart.getDate() - 7);
    const windowEnd = new Date();

    await this.pool.query(
      `INSERT INTO slo_status (status_id, slo_id, window_start, window_end, budget_consumed_percentage, budget_remaining_percentage, measurement_count, avg_value)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
       ON CONFLICT (slo_id, window_start) DO UPDATE SET
         budget_consumed_percentage = $5,
         budget_remaining_percentage = $6,
         measurement_count = $7,
         avg_value = $8`,
      [
        uuidv4(),
        sloId,
        windowStart,
        windowEnd,
        budgetConsumedPercentage,
        100 - budgetConsumedPercentage,
        measurementCount,
        avgValue,
      ]
    );
  }
}
