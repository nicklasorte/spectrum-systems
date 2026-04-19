import { Pool } from "pg";

/**
 * Postmortem enforcement
 * BLOCK on missing postmortem
 */

export async function enforcePostmortemRequired(
  pool: Pool,
  failedArtifactId: string,
  failureTime: Date
): Promise<{ has_postmortem: boolean; postmortem_id?: string; action: "allow" | "block" }> {
  const result = await pool.query(
    `SELECT artifact_id FROM artifacts
     WHERE artifact_kind = 'postmortem_artifact'
     AND failed_artifact_id = $1
     AND created_at > $2 - INTERVAL '24 hours'
     LIMIT 1`,
    [failedArtifactId, failureTime]
  );

  if (result.rows.length > 0) {
    return {
      has_postmortem: true,
      postmortem_id: result.rows[0].artifact_id,
      action: "allow",
    };
  }

  return {
    has_postmortem: false,
    action: "block",
  };
}

export async function validateExceptionNotExpired(
  pool: Pool,
  exceptionId: string
): Promise<{ is_valid: boolean; reason?: string }> {
  const result = await pool.query(
    `SELECT expiry_date FROM exception_artifacts WHERE exception_id = $1`,
    [exceptionId]
  );

  if (result.rows.length === 0) {
    return { is_valid: false, reason: "Exception not found" };
  }

  const expiryDate = new Date(result.rows[0].expiry_date);
  if (expiryDate < new Date()) {
    return { is_valid: false, reason: "Exception expired" };
  }

  return { is_valid: true };
}

export async function validateConvertedPolicyExists(
  pool: Pool,
  exceptionId: string
): Promise<boolean> {
  const result = await pool.query(
    `SELECT converted_artifact_ids FROM exception_artifacts WHERE exception_id = $1`,
    [exceptionId]
  );

  if (result.rows.length === 0) return false;

  const ids = JSON.parse(result.rows[0].converted_artifact_ids || "[]");
  if (ids.length === 0) return false;

  const policyResult = await pool.query(
    `SELECT COUNT(*) FROM artifacts WHERE artifact_kind = 'policy_definition' AND artifact_id = ANY($1::uuid[])`,
    [ids]
  );

  return parseInt(policyResult.rows[0].count) > 0;
}
