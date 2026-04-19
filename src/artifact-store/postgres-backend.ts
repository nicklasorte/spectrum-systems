import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * PostgreSQL backend for artifact store
 * Pure data infrastructure — no decision logic
 */

export interface PostgresStorageConfig {
  pgHost: string;
  pgPort: number;
  pgDatabase: string;
  pgUser: string;
  pgPassword: string;
}

export class PostgresStorageBackend {
  private pool: Pool;

  constructor(config: PostgresStorageConfig) {
    this.pool = new Pool({
      host: config.pgHost,
      port: config.pgPort,
      database: config.pgDatabase,
      user: config.pgUser,
      password: config.pgPassword,
    });
  }

  async initialize(): Promise<void> {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS artifacts (
        artifact_id UUID PRIMARY KEY,
        artifact_kind VARCHAR(255) NOT NULL,
        created_at TIMESTAMP NOT NULL,
        schema_ref VARCHAR(255),
        trace_id UUID,
        content_hash VARCHAR(255) NOT NULL,
        payload JSONB,
        created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
      CREATE INDEX IF NOT EXISTS idx_artifact_kind ON artifacts(artifact_kind);
      CREATE INDEX IF NOT EXISTS idx_trace_id ON artifacts(trace_id);
      CREATE INDEX IF NOT EXISTS idx_created_at ON artifacts(created_at);
    `);

    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS audit_entries (
        entry_id UUID PRIMARY KEY,
        event_type VARCHAR(255) NOT NULL,
        artifact_id UUID,
        outcome VARCHAR(50),
        reason_codes TEXT[],
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        actor VARCHAR(255),
        details JSONB
      );
      CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_entries(event_type);
      CREATE INDEX IF NOT EXISTS idx_audit_artifact_id ON audit_entries(artifact_id);
      CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_entries(created_at);
    `);

    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS exception_records (
        exception_id UUID PRIMARY KEY,
        artifact_id UUID NOT NULL,
        owner VARCHAR(255) NOT NULL,
        reason TEXT NOT NULL,
        expiry_date TIMESTAMP NOT NULL,
        supersedes UUID,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status VARCHAR(50) DEFAULT 'active'
      );
      CREATE INDEX IF NOT EXISTS idx_exception_artifact ON exception_records(artifact_id);
      CREATE INDEX IF NOT EXISTS idx_exception_owner ON exception_records(owner);
      CREATE INDEX IF NOT EXISTS idx_exception_expiry ON exception_records(expiry_date);
    `);
  }

  async store(artifact: any): Promise<void> {
    await this.pool.query(
      `INSERT INTO artifacts (artifact_id, artifact_kind, created_at, schema_ref, trace_id, content_hash, payload)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       ON CONFLICT (artifact_id) DO NOTHING`,
      [
        artifact.artifact_id,
        artifact.artifact_kind,
        artifact.created_at,
        artifact.schema_ref,
        artifact.trace?.trace_id,
        artifact.content_hash || "unknown",
        JSON.stringify(artifact),
      ]
    );
  }

  async retrieve(artifactId: string): Promise<any | null> {
    const result = await this.pool.query(
      `SELECT payload FROM artifacts WHERE artifact_id = $1`,
      [artifactId]
    );

    if (result.rows.length === 0) return null;
    return result.rows[0].payload;
  }

  async writeAuditEntry(
    artifactId: string,
    eventType: string,
    outcome: string,
    reasonCodes: string[],
    actor: string,
    details?: any
  ): Promise<void> {
    await this.pool.query(
      `INSERT INTO audit_entries (entry_id, event_type, artifact_id, outcome, reason_codes, actor, details)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        uuidv4(),
        eventType,
        artifactId,
        outcome,
        reasonCodes,
        actor,
        JSON.stringify(details || {}),
      ]
    );
  }

  async readAuditEntries(artifactId?: string, limit: number = 100): Promise<any[]> {
    let query = `SELECT * FROM audit_entries`;
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

  async writeExceptionRecord(
    artifactId: string,
    owner: string,
    reason: string,
    expiryDays: number = 30
  ): Promise<void> {
    const expiryDate = new Date();
    expiryDate.setDate(expiryDate.getDate() + expiryDays);

    await this.pool.query(
      `INSERT INTO exception_records (exception_id, artifact_id, owner, reason, expiry_date)
       VALUES ($1, $2, $3, $4, $5)`,
      [uuidv4(), artifactId, owner, reason, expiryDate]
    );
  }

  async readExceptionBacklog(): Promise<any[]> {
    const result = await this.pool.query(
      `SELECT * FROM exception_records WHERE status = 'active' AND expiry_date > NOW() ORDER BY created_at DESC`
    );
    return result.rows;
  }

  async readExceptionCount(): Promise<number> {
    const result = await this.pool.query(
      `SELECT COUNT(*) as count FROM exception_records WHERE status = 'active' AND expiry_date > NOW()`
    );
    return parseInt(result.rows[0].count);
  }

  async close(): Promise<void> {
    await this.pool.end();
  }
}
