import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Playbook Execution Tracking
 * Addresses red team finding on execution auditing
 */

export interface PlaybookExecution {
  execution_id: string;
  playbook_id: string;
  triggered_by_signal_id: string;
  step_executions: StepExecution[];
  started_at: string;
  completed_at?: string;
  status: "in_progress" | "completed" | "failed";
}

export interface StepExecution {
  step_id: string;
  executed_by: string;
  started_at: string;
  completed_at?: string;
  outcome: string;
  notes?: string;
}

export async function initializePlaybookTables(pool: Pool): Promise<void> {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS playbook_executions (
      execution_id UUID PRIMARY KEY,
      playbook_id UUID NOT NULL,
      triggered_by_signal_id UUID NOT NULL,
      status VARCHAR(50),
      started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      completed_at TIMESTAMP,
      INDEX idx_playbook_id (playbook_id),
      INDEX idx_status (status)
    )
  `);

  await pool.query(`
    CREATE TABLE IF NOT EXISTS step_executions (
      step_execution_id UUID PRIMARY KEY,
      execution_id UUID NOT NULL,
      step_id UUID NOT NULL,
      executed_by VARCHAR(255),
      started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      completed_at TIMESTAMP,
      outcome TEXT,
      notes TEXT,
      INDEX idx_execution_id (execution_id),
      INDEX idx_step_id (step_id)
    )
  `);
}

export async function trackPlaybookExecution(
  pool: Pool,
  playbookId: string,
  signalId: string
): Promise<string> {
  const executionId = uuidv4();

  await pool.query(
    `INSERT INTO playbook_executions (execution_id, playbook_id, triggered_by_signal_id, status)
     VALUES ($1, $2, $3, 'in_progress')`,
    [executionId, playbookId, signalId]
  );

  return executionId;
}

export async function recordStepCompletion(
  pool: Pool,
  executionId: string,
  stepId: string,
  executedBy: string,
  outcome: string,
  notes?: string
): Promise<void> {
  await pool.query(
    `INSERT INTO step_executions (step_execution_id, execution_id, step_id, executed_by, outcome, notes)
     VALUES ($1, $2, $3, $4, $5, $6)`,
    [uuidv4(), executionId, stepId, executedBy, outcome, notes]
  );
}

export async function completePlaybookExecution(
  pool: Pool,
  executionId: string
): Promise<void> {
  await pool.query(
    `UPDATE playbook_executions SET status = 'completed', completed_at = NOW() WHERE execution_id = $1`,
    [executionId]
  );
}

export async function getPlaybookExecution(
  pool: Pool,
  executionId: string
): Promise<PlaybookExecution | null> {
  const result = await pool.query(
    `SELECT * FROM playbook_executions WHERE execution_id = $1`,
    [executionId]
  );

  if (result.rows.length === 0) return null;

  const execution = result.rows[0];
  const stepsResult = await pool.query(
    `SELECT step_id, executed_by, started_at, completed_at, outcome, notes FROM step_executions WHERE execution_id = $1`,
    [executionId]
  );

  return {
    execution_id: execution.execution_id,
    playbook_id: execution.playbook_id,
    triggered_by_signal_id: execution.triggered_by_signal_id,
    started_at: execution.started_at,
    completed_at: execution.completed_at,
    status: execution.status,
    step_executions: stepsResult.rows,
  };
}
