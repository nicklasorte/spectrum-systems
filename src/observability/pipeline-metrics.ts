import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Pipeline Metrics Collector
 * Tracks: latency, cost, quality, bottlenecks
 */

export interface PipelineMetrics {
  run_id: string;
  timestamp: string;
  mvp_name: string;
  latency_ms: number;
  cost_cents: number;
  quality_score: number;
  status: "pass" | "warn" | "fail" | "block";
  trace_completeness: number;
}

export class PipelineMetricsCollector {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async initialize(): Promise<void> {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS pipeline_metrics (
        metric_id UUID PRIMARY KEY,
        run_id UUID NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        mvp_name VARCHAR(50) NOT NULL,
        latency_ms INT,
        cost_cents NUMERIC,
        quality_score NUMERIC,
        status VARCHAR(50),
        trace_completeness NUMERIC,
        INDEX idx_run_id (run_id),
        INDEX idx_mvp_name (mvp_name),
        INDEX idx_timestamp (timestamp)
      )
    `);
  }

  async recordMetric(metric: PipelineMetrics): Promise<void> {
    await this.pool.query(
      `INSERT INTO pipeline_metrics (metric_id, run_id, mvp_name, latency_ms, cost_cents, quality_score, status, trace_completeness)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
      [
        uuidv4(),
        metric.run_id,
        metric.mvp_name,
        metric.latency_ms,
        metric.cost_cents,
        metric.quality_score,
        metric.status,
        metric.trace_completeness,
      ]
    );
  }

  async getBottlenecks(limit: number = 10): Promise<any[]> {
    const result = await this.pool.query(
      `SELECT mvp_name, AVG(latency_ms) as avg_latency, STDDEV(latency_ms) as stddev_latency, COUNT(*) as run_count
       FROM pipeline_metrics
       WHERE timestamp > NOW() - INTERVAL '7 days'
       GROUP BY mvp_name
       ORDER BY avg_latency DESC
       LIMIT $1`,
      [limit]
    );
    return result.rows;
  }

  async getCostTrend(): Promise<any[]> {
    const result = await this.pool.query(
      `SELECT DATE(timestamp) as date, AVG(cost_cents) as avg_cost, MAX(cost_cents) as max_cost
       FROM pipeline_metrics
       WHERE timestamp > NOW() - INTERVAL '30 days'
       GROUP BY DATE(timestamp)
       ORDER BY date DESC`
    );
    return result.rows;
  }

  async getFailureRate(): Promise<number> {
    const result = await this.pool.query(
      `SELECT COUNT(CASE WHEN status IN ('fail', 'block') THEN 1 END)::float / COUNT(*) as failure_rate
       FROM pipeline_metrics
       WHERE timestamp > NOW() - INTERVAL '7 days'`
    );
    return result.rows[0]?.failure_rate || 0;
  }
}
