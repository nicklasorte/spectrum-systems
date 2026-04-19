import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Lineage Graph
 * Queryable dependency graph: artifact A caused by artifact B
 * Enables root cause tracing
 */

export interface LineageEdge {
  edge_id: string;
  source_artifact_id: string;
  target_artifact_id: string;
  relationship: "caused_by" | "depends_on" | "evaluated_by" | "input_to" | "triggered_by";
  created_at: string;
}

export interface LineageNode {
  artifact_id: string;
  artifact_kind: string;
  created_at: string;
  trace_id: string;
  in_degree: number;   // how many artifacts caused this
  out_degree: number;  // how many artifacts this caused
}

export class LineageGraph {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async initialize(): Promise<void> {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS lineage_edges (
        edge_id UUID PRIMARY KEY,
        source_artifact_id UUID NOT NULL,
        target_artifact_id UUID NOT NULL,
        relationship VARCHAR(50) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_source (source_artifact_id),
        INDEX idx_target (target_artifact_id),
        INDEX idx_relationship (relationship),
        UNIQUE(source_artifact_id, target_artifact_id, relationship)
      )
    `);

    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS lineage_metadata (
        artifact_id UUID PRIMARY KEY,
        artifact_kind VARCHAR(255),
        trace_id UUID,
        created_at TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_kind (artifact_kind),
        INDEX idx_trace_id (trace_id)
      )
    `);
  }

  async recordLineageEdge(
    sourceArtifactId: string,
    targetArtifactId: string,
    relationship: LineageEdge["relationship"]
  ): Promise<void> {
    await this.pool.query(
      `INSERT INTO lineage_edges (edge_id, source_artifact_id, target_artifact_id, relationship)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (source_artifact_id, target_artifact_id, relationship) DO NOTHING`,
      [uuidv4(), sourceArtifactId, targetArtifactId, relationship]
    );
  }

  async getInboundLineage(
    artifactId: string,
    maxDepth: number = 5
  ): Promise<LineageNode[]> {
    const result = await this.pool.query(
      `WITH RECURSIVE upstream AS (
        SELECT source_artifact_id, target_artifact_id, 1 as depth
        FROM lineage_edges
        WHERE target_artifact_id = $1

        UNION ALL

        SELECT e.source_artifact_id, e.target_artifact_id, u.depth + 1
        FROM lineage_edges e
        JOIN upstream u ON e.target_artifact_id = u.source_artifact_id
        WHERE u.depth < $2
      )
      SELECT DISTINCT source_artifact_id as artifact_id
      FROM upstream`,
      [artifactId, maxDepth]
    );

    return result.rows.map((r) => ({
      artifact_id: r.artifact_id,
      artifact_kind: "unknown",
      created_at: new Date().toISOString(),
      trace_id: uuidv4(),
      in_degree: 0,
      out_degree: 0,
    }));
  }

  async getOutboundLineage(
    artifactId: string,
    maxDepth: number = 5
  ): Promise<LineageNode[]> {
    const result = await this.pool.query(
      `WITH RECURSIVE downstream AS (
        SELECT source_artifact_id, target_artifact_id, 1 as depth
        FROM lineage_edges
        WHERE source_artifact_id = $1

        UNION ALL

        SELECT e.source_artifact_id, e.target_artifact_id, d.depth + 1
        FROM lineage_edges e
        JOIN downstream d ON e.source_artifact_id = d.target_artifact_id
        WHERE d.depth < $2
      )
      SELECT DISTINCT target_artifact_id as artifact_id
      FROM downstream`,
      [artifactId, maxDepth]
    );

    return result.rows.map((r) => ({
      artifact_id: r.artifact_id,
      artifact_kind: "unknown",
      created_at: new Date().toISOString(),
      trace_id: uuidv4(),
      in_degree: 0,
      out_degree: 0,
    }));
  }

  async getImpactedArtifacts(
    artifactId: string
  ): Promise<{ artifact_id: string; relationship: string }[]> {
    const result = await this.pool.query(
      `SELECT target_artifact_id as artifact_id, relationship
       FROM lineage_edges
       WHERE source_artifact_id = $1`,
      [artifactId]
    );

    return result.rows;
  }

  async getRootCauses(artifactId: string): Promise<LineageNode[]> {
    const result = await this.pool.query(
      `WITH RECURSIVE roots AS (
        SELECT source_artifact_id, 1 as depth
        FROM lineage_edges
        WHERE target_artifact_id = $1 AND relationship IN ('caused_by', 'triggered_by')

        UNION ALL

        SELECT e.source_artifact_id, r.depth + 1
        FROM lineage_edges e
        JOIN roots r ON e.target_artifact_id = r.source_artifact_id
        WHERE r.depth < 10 AND e.relationship IN ('caused_by', 'triggered_by')
      )
      SELECT DISTINCT source_artifact_id as artifact_id
      FROM roots
      WHERE NOT EXISTS (
        SELECT 1 FROM lineage_edges e2
        WHERE e2.target_artifact_id = roots.source_artifact_id
        AND e2.relationship IN ('caused_by', 'triggered_by')
      )`,
      [artifactId]
    );

    return result.rows.map((r) => ({
      artifact_id: r.artifact_id,
      artifact_kind: "unknown",
      created_at: new Date().toISOString(),
      trace_id: uuidv4(),
      in_degree: 0,
      out_degree: 0,
    }));
  }

  async recordLineageMetadata(
    artifactId: string,
    artifactKind: string,
    traceId: string,
    createdAt: Date
  ): Promise<void> {
    await this.pool.query(
      `INSERT INTO lineage_metadata (artifact_id, artifact_kind, trace_id, created_at)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (artifact_id) DO UPDATE SET updated_at = NOW()`,
      [artifactId, artifactKind, traceId, createdAt]
    );
  }
}
