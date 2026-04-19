import { Pool, QueryResult } from "pg";
import * as AWS from "aws-sdk";
import { v4 as uuidv4 } from "uuid";

/**
 * PostgreSQL backend for artifact store
 * All artifacts stored as immutable records with content hash
 */

export interface PostgresStorageConfig {
  pgHost: string;
  pgPort: number;
  pgDatabase: string;
  pgUser: string;
  pgPassword: string;
  s3Bucket: string;
  s3Region: string;
}

export class PostgresStorageBackend {
  private pool: Pool;
  private s3: AWS.S3;

  constructor(config: PostgresStorageConfig) {
    this.pool = new Pool({
      host: config.pgHost,
      port: config.pgPort,
      database: config.pgDatabase,
      user: config.pgUser,
      password: config.pgPassword,
    });

    this.s3 = new AWS.S3({
      region: config.s3Region,
      s3BucketEndpoint: true,
    });
  }

  async initialize(): Promise<void> {
    // Create artifacts table
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS artifacts (
        artifact_id UUID PRIMARY KEY,
        artifact_kind VARCHAR(255) NOT NULL,
        created_at TIMESTAMP NOT NULL,
        schema_ref VARCHAR(255),
        trace_id UUID,
        content_hash VARCHAR(255) NOT NULL,
        s3_key VARCHAR(1024) NOT NULL,
        payload JSONB,
        created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_artifact_kind (artifact_kind),
        INDEX idx_trace_id (trace_id),
        INDEX idx_created_at (created_at)
      )
    `);

    // Create audit log table
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS audit_log (
        log_id UUID PRIMARY KEY,
        event_type VARCHAR(255) NOT NULL,
        artifact_id UUID,
        decision_outcome VARCHAR(50),
        reason_codes TEXT[],
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        actor VARCHAR(255),
        details JSONB,
        INDEX idx_event_type (event_type),
        INDEX idx_artifact_id (artifact_id),
        INDEX idx_created_at (created_at)
      )
    `);

    // Create override tracking table
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS overrides (
        override_id UUID PRIMARY KEY,
        artifact_id UUID NOT NULL,
        owner VARCHAR(255) NOT NULL,
        reason TEXT NOT NULL,
        expiry_date TIMESTAMP NOT NULL,
        supersedes UUID,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status VARCHAR(50) DEFAULT 'active',
        INDEX idx_artifact_id (artifact_id),
        INDEX idx_owner (owner),
        INDEX idx_expiry_date (expiry_date)
      )
    `);
  }

  async store(artifact: any): Promise<void> {
    const artifactId = artifact.artifact_id;
    const s3Key = `artifacts/${artifactId}`;

    // Store payload in S3
    await this.s3
      .putObject({
        Bucket: process.env.S3_BUCKET!,
        Key: s3Key,
        Body: JSON.stringify(artifact),
        ContentType: "application/json",
      })
      .promise();

    // Store metadata in PostgreSQL
    await this.pool.query(
      `INSERT INTO artifacts (artifact_id, artifact_kind, created_at, schema_ref, trace_id, content_hash, s3_key, payload)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
      [
        artifactId,
        artifact.artifact_kind,
        artifact.created_at,
        artifact.schema_ref,
        artifact.trace?.trace_id,
        artifact.content_hash || "unknown",
        s3Key,
        JSON.stringify(artifact),
      ]
    );
  }

  async retrieve(artifactId: string): Promise<any | null> {
    const result = await this.pool.query(
      `SELECT s3_key FROM artifacts WHERE artifact_id = $1`,
      [artifactId]
    );

    if (result.rows.length === 0) return null;

    const s3Key = result.rows[0].s3_key;
    const s3Result = await this.s3
      .getObject({
        Bucket: process.env.S3_BUCKET!,
        Key: s3Key,
      })
      .promise();

    return JSON.parse(s3Result.Body?.toString() || "{}");
  }

  async logDecision(
    artifactId: string,
    outcome: string,
    reasonCodes: string[],
    actor: string,
    details?: any
  ): Promise<void> {
    await this.pool.query(
      `INSERT INTO audit_log (log_id, event_type, artifact_id, decision_outcome, reason_codes, actor, details)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        uuidv4(),
        "control_decision",
        artifactId,
        outcome,
        reasonCodes,
        actor,
        JSON.stringify(details || {}),
      ]
    );
  }

  async recordOverride(
    artifactId: string,
    owner: string,
    reason: string,
    expiryDays: number = 30
  ): Promise<void> {
    const expiryDate = new Date();
    expiryDate.setDate(expiryDate.getDate() + expiryDays);

    await this.pool.query(
      `INSERT INTO overrides (override_id, artifact_id, owner, reason, expiry_date)
       VALUES ($1, $2, $3, $4, $5)`,
      [uuidv4(), artifactId, owner, reason, expiryDate]
    );
  }

  async getAuditLog(
    artifactId?: string,
    limit: number = 100
  ): Promise<any[]> {
    let query = `SELECT * FROM audit_log`;
    const params: any[] = [];

    if (artifactId) {
      query += ` WHERE artifact_id = $1`;
      params.push(artifactId);
    }

    query += ` ORDER BY created_at DESC LIMIT $${params.length + 1}`;
    params.push(limit);

    const result = await this.pool.query(query, params);
    return result.rows;
  }

  async getOverrideBacklog(): Promise<any[]> {
    const result = await this.pool.query(
      `SELECT * FROM overrides WHERE status = 'active' AND expiry_date > NOW() ORDER BY created_at DESC`
    );
    return result.rows;
  }

  async getOverrideCount(): Promise<number> {
    const result = await this.pool.query(
      `SELECT COUNT(*) as count FROM overrides WHERE status = 'active' AND expiry_date > NOW()`
    );
    return parseInt(result.rows[0].count);
  }

  async close(): Promise<void> {
    await this.pool.end();
  }
}
