import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Artifact Intelligence Layer
 * Read-only searchable index of all artifacts
 * Exposes control signals (SLI status, drift signals, exceptions)
 */

export interface ArtifactQuery {
  artifact_kind?: string;
  trace_id?: string;
  created_after?: Date;
  created_before?: Date;
  dimensions?: Record<string, string>;
  limit?: number;
}

export interface ArtifactSearchResult {
  artifact_id: string;
  artifact_kind: string;
  created_at: string;
  trace_id: string;
  status?: string;
  dimensions?: Record<string, string>;
}

export interface ControlSignal {
  signal_type: "sli_status" | "drift_signal" | "exception_backlog" | "policy_health";
  severity: "info" | "warning" | "critical";
  context: string;
  linked_playbook?: string;
}

export class ArtifactIntelligence {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async initialize(): Promise<void> {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS artifact_search_index (
        index_id UUID PRIMARY KEY,
        artifact_id UUID NOT NULL,
        artifact_kind VARCHAR(255),
        trace_id UUID,
        created_at TIMESTAMP,
        dimensions JSONB,
        status VARCHAR(50),
        created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_artifact_id (artifact_id),
        INDEX idx_artifact_kind (artifact_kind),
        INDEX idx_trace_id (trace_id),
        INDEX idx_created_at (created_at),
        INDEX idx_status (status)
      )
    `);

    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS control_signals (
        signal_id UUID PRIMARY KEY,
        signal_type VARCHAR(50) NOT NULL,
        severity VARCHAR(50) NOT NULL,
        context TEXT,
        linked_playbook VARCHAR(255),
        artifact_id UUID,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_signal_type (signal_type),
        INDEX idx_severity (severity),
        INDEX idx_artifact_id (artifact_id)
      )
    `);
  }

  async indexArtifact(
    artifactId: string,
    artifactKind: string,
    traceId: string,
    createdAt: Date,
    dimensions?: Record<string, string>,
    status?: string
  ): Promise<void> {
    await this.pool.query(
      `INSERT INTO artifact_search_index (index_id, artifact_id, artifact_kind, trace_id, created_at, dimensions, status)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        uuidv4(),
        artifactId,
        artifactKind,
        traceId,
        createdAt,
        dimensions ? JSON.stringify(dimensions) : null,
        status,
      ]
    );
  }

  async search(query: ArtifactQuery): Promise<ArtifactSearchResult[]> {
    let sql = `SELECT artifact_id, artifact_kind, created_at, trace_id, status, dimensions
               FROM artifact_search_index WHERE 1=1`;
    const params: any[] = [];

    if (query.artifact_kind) {
      sql += ` AND artifact_kind = $${params.length + 1}`;
      params.push(query.artifact_kind);
    }

    if (query.trace_id) {
      sql += ` AND trace_id = $${params.length + 1}`;
      params.push(query.trace_id);
    }

    if (query.created_after) {
      sql += ` AND created_at >= $${params.length + 1}`;
      params.push(query.created_after);
    }

    if (query.created_before) {
      sql += ` AND created_at <= $${params.length + 1}`;
      params.push(query.created_before);
    }

    if (query.dimensions) {
      for (const [key, value] of Object.entries(query.dimensions)) {
        sql += ` AND dimensions->$${params.length + 1} = $${params.length + 2}`;
        params.push(key, value);
      }
    }

    sql += ` ORDER BY created_at DESC`;
    if (query.limit) {
      sql += ` LIMIT $${params.length + 1}`;
      params.push(query.limit);
    }

    const result = await this.pool.query(sql, params);

    return result.rows.map((r) => ({
      artifact_id: r.artifact_id,
      artifact_kind: r.artifact_kind,
      created_at: r.created_at,
      trace_id: r.trace_id,
      status: r.status,
      dimensions: r.dimensions ? JSON.parse(r.dimensions) : undefined,
    }));
  }

  async recordControlSignal(
    signalType: ControlSignal["signal_type"],
    severity: ControlSignal["severity"],
    context: string,
    artifactId?: string,
    linkedPlaybook?: string
  ): Promise<void> {
    await this.pool.query(
      `INSERT INTO control_signals (signal_id, signal_type, severity, context, artifact_id, linked_playbook)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [uuidv4(), signalType, severity, context, artifactId, linkedPlaybook]
    );
  }

  async getControlSignals(
    artifactId?: string,
    minSeverity?: string
  ): Promise<ControlSignal[]> {
    let sql = `SELECT signal_type, severity, context, linked_playbook FROM control_signals WHERE 1=1`;
    const params: any[] = [];

    if (artifactId) {
      sql += ` AND artifact_id = $${params.length + 1}`;
      params.push(artifactId);
    }

    if (minSeverity) {
      const severityOrder = { info: 0, warning: 1, critical: 2 };
      const minOrder = severityOrder[minSeverity as keyof typeof severityOrder] || 0;
      sql += ` AND CASE severity WHEN 'info' THEN 0 WHEN 'warning' THEN 1 WHEN 'critical' THEN 2 END >= $${params.length + 1}`;
      params.push(minOrder);
    }

    sql += ` ORDER BY created_at DESC`;

    const result = await this.pool.query(sql, params);

    return result.rows;
  }
}
