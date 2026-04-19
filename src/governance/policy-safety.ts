import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Policy safety: immutability, versioning, auto-rollback
 */

export async function createImmutablePolicyVersion(
  pool: Pool,
  policyName: string,
  policyText: string,
  owner: string,
  previousVersionId?: string
): Promise<string> {
  // Fetch previous version to increment version number
  const prevResult = await pool.query(
    `SELECT MAX(policy_version) as max_version FROM policy_definitions WHERE policy_name = $1`,
    [policyName]
  );

  const nextVersion = (prevResult.rows[0]?.max_version || 0) + 1;
  const policyId = uuidv4();

  await pool.query(
    `INSERT INTO policy_definitions (policy_id, policy_name, policy_version, policy_text, owner, status, supersedes)
     VALUES ($1, $2, $3, $4, $5, 'draft', $6)`,
    [policyId, policyName, nextVersion, policyText, owner, previousVersionId]
  );

  return policyId;
}

export async function auditPolicyChanges(pool: Pool, policyId: string): Promise<number> {
  const result = await pool.query(
    `SELECT COUNT(*) FROM policy_eval_cases WHERE policy_id = $1`,
    [policyId]
  );

  return parseInt(result.rows[0].count);
}

export async function getIncidentTrendForPolicy(
  pool: Pool,
  policyId: string,
  windowDays: number = 7
): Promise<{ incident_count: number; trend: "increasing" | "stable" | "decreasing" }> {
  const result = await pool.query(
    `SELECT incidents_since_deployment FROM policy_definitions WHERE policy_id = $1`,
    [policyId]
  );

  const currentIncidents = result.rows[0]?.incidents_since_deployment || 0;

  // For now, simple calculation; in production, would track time-windowed incidents
  const trend: "increasing" | "stable" | "decreasing" = currentIncidents > 3 ? "increasing" : "stable";

  return { incident_count: currentIncidents, trend };
}

export async function autoRollbackIfNeeded(
  pool: Pool,
  policyId: string,
  incidentThreshold: number = 5
): Promise<boolean> {
  const result = await pool.query(
    `SELECT policy_version, supersedes FROM policy_definitions WHERE policy_id = $1`,
    [policyId]
  );

  if (result.rows.length === 0) return false;

  const { supersedes } = result.rows[0];
  const incidents = await pool.query(
    `SELECT incidents_since_deployment FROM policy_definitions WHERE policy_id = $1`,
    [policyId]
  );

  const incidentCount = incidents.rows[0]?.incidents_since_deployment || 0;

  if (incidentCount > incidentThreshold && supersedes) {
    // Auto-rollback: mark current as deprecated, reactivate previous
    await pool.query(
      `UPDATE policy_definitions SET status = 'deprecated' WHERE policy_id = $1`,
      [policyId]
    );

    await pool.query(
      `UPDATE policy_definitions SET status = 'active', rollout_percentage = 100 WHERE policy_id = $1`,
      [supersedes]
    );

    return true;
  }

  return false;
}
