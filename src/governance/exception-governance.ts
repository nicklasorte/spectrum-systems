import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Exception Governance
 * Track exceptions with expiry, conversion rules, sunset logic
 * (Renamed from "Override" to "Exception" for neutral language)
 */

export interface ExceptionArtifact {
  artifact_kind: "exception_artifact";
  artifact_id: string;
  target_artifact_id: string;
  owner: string;
  reason: string;
  exception_outcome: "allow" | "warn" | "freeze" | "block";
  created_at: string;
  expiry_date: string;
  supersedes?: string;
  conversion_status: "needs_conversion" | "converted_to_policy" | "converted_to_eval" | "retired";
  converted_artifact_ids?: string[];
  notes?: string;
}

export class ExceptionGovernor {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async initialize(): Promise<void> {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS exception_artifacts (
        exception_id UUID PRIMARY KEY,
        target_artifact_id UUID NOT NULL,
        owner VARCHAR(255) NOT NULL,
        reason TEXT NOT NULL,
        exception_outcome VARCHAR(50) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expiry_date TIMESTAMP NOT NULL,
        supersedes UUID,
        conversion_status VARCHAR(50) DEFAULT 'needs_conversion',
        converted_artifact_ids JSONB,
        notes TEXT,
        status VARCHAR(50) DEFAULT 'active',
        INDEX idx_target_artifact (target_artifact_id),
        INDEX idx_expiry_date (expiry_date),
        INDEX idx_conversion_status (conversion_status)
      )
    `);

    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS exception_backlog_audit (
        audit_id UUID PRIMARY KEY,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total_active_exceptions INT,
        overdue_exceptions INT,
        unconverted_exceptions INT,
        backlog_status VARCHAR(50),
        INDEX idx_checked_at (checked_at)
      )
    `);
  }

  async recordException(
    targetArtifactId: string,
    owner: string,
    reason: string,
    exceptionOutcome: "allow" | "warn" | "freeze" | "block",
    expiryDays: number = 30
  ): Promise<string> {
    const exceptionId = uuidv4();
    const expiryDate = new Date();
    expiryDate.setDate(expiryDate.getDate() + expiryDays);

    await this.pool.query(
      `INSERT INTO exception_artifacts (exception_id, target_artifact_id, owner, reason, exception_outcome, expiry_date)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [exceptionId, targetArtifactId, owner, reason, exceptionOutcome, expiryDate]
    );

    return exceptionId;
  }

  async getActiveExceptionBacklog(): Promise<number> {
    const result = await this.pool.query(
      `SELECT COUNT(*) as count FROM exception_artifacts
       WHERE status = 'active' AND expiry_date > NOW() AND conversion_status = 'needs_conversion'`
    );

    return parseInt(result.rows[0].count);
  }

  async getOverdueExceptions(): Promise<string[]> {
    const result = await this.pool.query(
      `SELECT exception_id FROM exception_artifacts
       WHERE status = 'active' AND expiry_date <= NOW()`
    );

    return result.rows.map((r) => r.exception_id);
  }

  async markExceptionAsConverted(
    exceptionId: string,
    conversionType: "policy" | "eval",
    convertedArtifactIds: string[]
  ): Promise<void> {
    const status = conversionType === "policy" ? "converted_to_policy" : "converted_to_eval";

    await this.pool.query(
      `UPDATE exception_artifacts
       SET conversion_status = $1, converted_artifact_ids = $2
       WHERE exception_id = $3`,
      [status, JSON.stringify(convertedArtifactIds), exceptionId]
    );
  }

  async retireException(exceptionId: string): Promise<void> {
    await this.pool.query(
      `UPDATE exception_artifacts SET status = 'retired', conversion_status = 'retired' WHERE exception_id = $1`,
      [exceptionId]
    );
  }

  async auditExceptionBacklog(): Promise<{
    total_active: number;
    overdue: number;
    unconverted: number;
    status: "healthy" | "warning" | "critical";
  }> {
    const totalResult = await this.pool.query(
      `SELECT COUNT(*) as count FROM exception_artifacts WHERE status = 'active' AND expiry_date > NOW()`
    );

    const overdueResult = await this.pool.query(
      `SELECT COUNT(*) as count FROM exception_artifacts WHERE status = 'active' AND expiry_date <= NOW()`
    );

    const unconvertedResult = await this.pool.query(
      `SELECT COUNT(*) as count FROM exception_artifacts WHERE conversion_status = 'needs_conversion' AND status = 'active'`
    );

    const totalActive = parseInt(totalResult.rows[0].count);
    const overdue = parseInt(overdueResult.rows[0].count);
    const unconverted = parseInt(unconvertedResult.rows[0].count);

    let status: "healthy" | "warning" | "critical" = "healthy";
    if (unconverted > 5 || overdue > 0) status = "warning";
    if (unconverted > 10 || overdue > 5) status = "critical";

    await this.pool.query(
      `INSERT INTO exception_backlog_audit (audit_id, total_active_exceptions, overdue_exceptions, unconverted_exceptions, backlog_status)
       VALUES ($1, $2, $3, $4, $5)`,
      [uuidv4(), totalActive, overdue, unconverted, status]
    );

    return {
      total_active: totalActive,
      overdue,
      unconverted,
      status,
    };
  }
}
