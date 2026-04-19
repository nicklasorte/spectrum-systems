import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Judge Calibration Tracking
 * Monitor reviewer bias, consistency, drift
 */

export interface ReviewerStats {
  reviewer_id: string;
  review_count: number;
  approval_rate: number;
  avg_issue_count: number;
  bias_score: number; // 0-100, 50 = neutral
  consistency_score: number; // 0-100, 100 = very consistent
  last_review_at: string;
}

export interface CalibrationAlert {
  alert_id: string;
  reviewer_id: string;
  alert_type: "approval_rate_drift" | "consistency_drift" | "bias_detected";
  severity: "warning" | "critical";
  context: string;
}

export class JudgeCalibrationTracker {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async initialize(): Promise<void> {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS reviewer_stats (
        reviewer_id VARCHAR(255) PRIMARY KEY,
        review_count INT DEFAULT 0,
        approval_rate NUMERIC DEFAULT 50,
        avg_issue_count NUMERIC DEFAULT 5,
        bias_score NUMERIC DEFAULT 50,
        consistency_score NUMERIC DEFAULT 75,
        last_review_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_reviewer_id (reviewer_id)
      )
    `);

    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS calibration_alerts (
        alert_id UUID PRIMARY KEY,
        reviewer_id VARCHAR(255) NOT NULL,
        alert_type VARCHAR(50) NOT NULL,
        severity VARCHAR(50) NOT NULL,
        context TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_reviewer_id (reviewer_id),
        INDEX idx_alert_type (alert_type)
      )
    `);
  }

  async recordReview(
    reviewerId: string,
    approved: boolean,
    issueCount: number
  ): Promise<void> {
    const approvalDelta = approved ? 1 : 0;

    await this.pool.query(
      `INSERT INTO reviewer_stats (reviewer_id, review_count, approval_rate, avg_issue_count)
       VALUES ($1, 1, $2, $3)
       ON CONFLICT (reviewer_id) DO UPDATE SET
         review_count = review_count + 1,
         approval_rate = (approval_rate * (review_count) + $2) / (review_count + 1),
         avg_issue_count = (avg_issue_count * (review_count) + $3) / (review_count + 1),
         last_review_at = NOW()`,
      [reviewerId, approvalDelta * 100, issueCount]
    );
  }

  async getReviewerStats(reviewerId: string): Promise<ReviewerStats | null> {
    const result = await this.pool.query(
      `SELECT * FROM reviewer_stats WHERE reviewer_id = $1`,
      [reviewerId]
    );

    if (result.rows.length === 0) return null;
    return result.rows[0];
  }

  async detectCalibrationDrift(
    reviewerId: string
  ): Promise<CalibrationAlert[]> {
    const stats = await this.getReviewerStats(reviewerId);
    if (!stats) return [];

    const alerts: CalibrationAlert[] = [];

    // Approval rate drift: deviation > 20% from team median
    if (Math.abs(stats.approval_rate - 50) > 20) {
      alerts.push({
        alert_id: uuidv4(),
        reviewer_id: reviewerId,
        alert_type: "approval_rate_drift",
        severity: Math.abs(stats.approval_rate - 50) > 30 ? "critical" : "warning",
        context: `Approval rate ${stats.approval_rate.toFixed(1)}% (team median 50%)`,
      });
    }

    // Consistency drift: consistency < 70%
    if (stats.consistency_score < 70) {
      alerts.push({
        alert_id: uuidv4(),
        reviewer_id: reviewerId,
        alert_type: "consistency_drift",
        severity: stats.consistency_score < 60 ? "critical" : "warning",
        context: `Consistency score ${stats.consistency_score.toFixed(1)}% (target 75%+)`,
      });
    }

    // Bias detected: bias_score very far from 50
    if (Math.abs(stats.bias_score - 50) > 25) {
      alerts.push({
        alert_id: uuidv4(),
        reviewer_id: reviewerId,
        alert_type: "bias_detected",
        severity: "warning",
        context: `Bias score ${stats.bias_score.toFixed(1)} (neutral = 50)`,
      });
    }

    return alerts;
  }
}
