import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";
import type { PolicyDefinition } from "./policy-schema";

/**
 * Policy Engine
 * Manages policy lifecycle: draft → tested → deployed → active
 */

export class PolicyEngine {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async initialize(): Promise<void> {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS policy_definitions (
        policy_id UUID PRIMARY KEY,
        policy_name VARCHAR(255) NOT NULL,
        policy_version INT NOT NULL,
        policy_text TEXT NOT NULL,
        owner VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        supersedes UUID,
        status VARCHAR(50) DEFAULT 'draft',
        test_cases_count INT DEFAULT 0,
        test_pass_rate NUMERIC DEFAULT 0,
        rollout_percentage INT DEFAULT 0,
        rollout_started_at TIMESTAMP,
        incidents_since_deployment INT DEFAULT 0,
        UNIQUE(policy_name, policy_version),
        INDEX idx_policy_name (policy_name),
        INDEX idx_status (status)
      )
    `);

    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS policy_eval_cases (
        eval_case_id UUID PRIMARY KEY,
        policy_id UUID NOT NULL,
        test_input JSONB,
        expected_output VARCHAR(50),
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_policy_id (policy_id)
      )
    `);

    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS policy_eval_results (
        result_id UUID PRIMARY KEY,
        policy_id UUID NOT NULL,
        eval_case_id UUID NOT NULL,
        actual_output VARCHAR(50),
        matches_expected BOOLEAN,
        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_policy_id (policy_id),
        INDEX idx_eval_case_id (eval_case_id)
      )
    `);
  }

  async deployPolicy(
    policyId: string,
    initialRolloutPercentage: number = 10
  ): Promise<void> {
    const testResult = await this.pool.query(
      `SELECT COUNT(*) as total, COUNT(CASE WHEN matches_expected = true THEN 1 END) as passed
       FROM policy_eval_results WHERE policy_id = $1`,
      [policyId]
    );

    const total = parseInt(testResult.rows[0].total);
    const passed = parseInt(testResult.rows[0].passed);

    if (total === 0 || passed < total) {
      throw new Error(
        `Cannot deploy policy ${policyId}: test failures detected (${passed}/${total} passed)`
      );
    }

    await this.pool.query(
      `UPDATE policy_definitions
       SET status = 'active', rollout_percentage = $1, rollout_started_at = NOW()
       WHERE policy_id = $2`,
      [initialRolloutPercentage, policyId]
    );
  }

  async rolloutPolicy(policyId: string, newRolloutPercentage: number): Promise<void> {
    if (newRolloutPercentage < 0 || newRolloutPercentage > 100) {
      throw new Error("Rollout percentage must be 0-100");
    }

    await this.pool.query(
      `UPDATE policy_definitions SET rollout_percentage = $1 WHERE policy_id = $2`,
      [newRolloutPercentage, policyId]
    );
  }

  async recordPolicyIncident(policyId: string): Promise<void> {
    await this.pool.query(
      `UPDATE policy_definitions SET incidents_since_deployment = incidents_since_deployment + 1 WHERE policy_id = $1`,
      [policyId]
    );
  }

  async getPoliciesByStatus(status: string): Promise<PolicyDefinition[]> {
    const result = await this.pool.query(
      `SELECT * FROM policy_definitions WHERE status = $1 ORDER BY created_at DESC`,
      [status]
    );

    return result.rows;
  }
}
