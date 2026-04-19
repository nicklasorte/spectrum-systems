import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * A/B Testing Framework
 * Compare policy versions with statistical confidence
 */

export interface ABTest {
  test_id: string;
  policy_a_id: string;
  policy_b_id: string;
  metric_name: string;
  start_time: string;
  end_time?: string;
  status: "running" | "completed";
  sample_size_a: number;
  sample_size_b: number;
  mean_a: number;
  mean_b: number;
  p_value: number;
  winner?: "A" | "B";
  confidence_level: number;
}

export class ABTestFramework {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async initialize(): Promise<void> {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS ab_tests (
        test_id UUID PRIMARY KEY,
        policy_a_id VARCHAR(255) NOT NULL,
        policy_b_id VARCHAR(255) NOT NULL,
        metric_name VARCHAR(255) NOT NULL,
        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end_time TIMESTAMP,
        status VARCHAR(50) DEFAULT 'running',
        sample_size_a INT DEFAULT 0,
        sample_size_b INT DEFAULT 0,
        mean_a NUMERIC DEFAULT 0,
        mean_b NUMERIC DEFAULT 0,
        p_value NUMERIC,
        winner VARCHAR(1),
        confidence_level NUMERIC DEFAULT 0.95,
        INDEX idx_policy_a (policy_a_id),
        INDEX idx_policy_b (policy_b_id)
      )
    `);
  }

  async createTest(
    policyAId: string,
    policyBId: string,
    metricName: string
  ): Promise<string> {
    const testId = uuidv4();

    await this.pool.query(
      `INSERT INTO ab_tests (test_id, policy_a_id, policy_b_id, metric_name, status)
       VALUES ($1, $2, $3, $4, 'running')`,
      [testId, policyAId, policyBId, metricName]
    );

    return testId;
  }

  async analyzeTest(testId: string): Promise<ABTest | null> {
    const result = await this.pool.query(
      `SELECT * FROM ab_tests WHERE test_id = $1`,
      [testId]
    );

    if (result.rows.length === 0) return null;
    return result.rows[0];
  }

  async concludeTest(
    testId: string,
    winner: "A" | "B" | null
  ): Promise<void> {
    await this.pool.query(
      `UPDATE ab_tests SET status = 'completed', winner = $2, end_time = NOW()
       WHERE test_id = $1`,
      [testId, winner]
    );
  }
}
