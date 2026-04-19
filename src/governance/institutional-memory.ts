import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Institutional Memory
 * Store and retrieve past decisions (precedents)
 */

export interface Precedent {
  precedent_id: string;
  decision_type: string;
  context: Record<string, any>;
  outcome: string;
  reasoning: string;
  created_at: string;
  status: "active" | "superseded" | "deprecated";
}

export class InstitutionalMemory {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async initialize(): Promise<void> {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS precedents (
        precedent_id UUID PRIMARY KEY,
        decision_type VARCHAR(255) NOT NULL,
        context JSONB,
        outcome TEXT NOT NULL,
        reasoning TEXT NOT NULL,
        status VARCHAR(50) DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_decision_type (decision_type),
        INDEX idx_status (status)
      )
    `);
  }

  async recordPrecedent(
    decisionType: string,
    context: Record<string, any>,
    outcome: string,
    reasoning: string
  ): Promise<string> {
    const precedentId = uuidv4();

    await this.pool.query(
      `INSERT INTO precedents (precedent_id, decision_type, context, outcome, reasoning, status)
       VALUES ($1, $2, $3, $4, $5, 'active')`,
      [
        precedentId,
        decisionType,
        JSON.stringify(context),
        outcome,
        reasoning,
      ]
    );

    return precedentId;
  }

  async findRelevantPrecedents(
    decisionType: string
  ): Promise<Precedent[]> {
    const result = await this.pool.query(
      `SELECT * FROM precedents
       WHERE decision_type = $1 AND status = 'active'
       ORDER BY created_at DESC`,
      [decisionType]
    );

    return result.rows.map((row: any) => ({
      ...row,
      context: typeof row.context === 'string' ? JSON.parse(row.context) : row.context,
    }));
  }

  async supersedePrecedent(
    oldPrecedentId: string,
    newPrecedentId: string
  ): Promise<void> {
    await this.pool.query(
      `UPDATE precedents SET status = 'superseded' WHERE precedent_id = $1`,
      [oldPrecedentId]
    );
  }
}
