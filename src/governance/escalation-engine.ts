import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Escalation Engine
 * Routes alerts based on severity level
 */

export interface EscalationRule {
  severity: "warn" | "freeze" | "block";
  channel: "log" | "alert" | "page" | "escalate";
  recipients: string[];
  message_template: string;
}

export interface EscalationEvent {
  event_id: string;
  signal_type: string;
  severity: string;
  message: string;
  channel: string;
  recipients: string[];
  escalated_at: string;
  acknowledged_at?: string;
  status: "sent" | "acknowledged" | "failed";
}

export const DEFAULT_ESCALATION_RULES: EscalationRule[] = [
  {
    severity: "warn",
    channel: "log",
    recipients: [],
    message_template: "Warning: {signal_type} detected. {context}",
  },
  {
    severity: "freeze",
    channel: "alert",
    recipients: ["ops@team.com"],
    message_template: "FREEZE triggered: {signal_type}. Immediate action required. {context}",
  },
  {
    severity: "block",
    channel: "page",
    recipients: ["oncall@team.com", "lead@team.com"],
    message_template: "CRITICAL: {signal_type}. Pipeline blocked. {context}",
  },
];

export class EscalationEngine {
  private pool: Pool;
  private rules: Map<string, EscalationRule> = new Map();

  constructor(pool: Pool) {
    this.pool = pool;
    for (const rule of DEFAULT_ESCALATION_RULES) {
      this.rules.set(rule.severity, rule);
    }
  }

  async initialize(): Promise<void> {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS escalation_events (
        event_id UUID PRIMARY KEY,
        signal_type VARCHAR(255) NOT NULL,
        severity VARCHAR(50) NOT NULL,
        message TEXT,
        channel VARCHAR(50),
        recipients TEXT[],
        escalated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        acknowledged_at TIMESTAMP,
        status VARCHAR(50) DEFAULT 'sent',
        INDEX idx_severity (severity),
        INDEX idx_escalated_at (escalated_at)
      )
    `);
  }

  async escalate(
    signalType: string,
    severity: "warn" | "freeze" | "block",
    context: string
  ): Promise<EscalationEvent> {
    const rule = this.rules.get(severity);
    if (!rule) {
      throw new Error(`No escalation rule for severity ${severity}`);
    }

    const message = rule.message_template
      .replace("{signal_type}", signalType)
      .replace("{context}", context);

    const event: EscalationEvent = {
      event_id: uuidv4(),
      signal_type: signalType,
      severity,
      message,
      channel: rule.channel,
      recipients: rule.recipients,
      escalated_at: new Date().toISOString(),
      status: "sent",
    };

    await this.pool.query(
      `INSERT INTO escalation_events (event_id, signal_type, severity, message, channel, recipients, status)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        event.event_id,
        signalType,
        severity,
        message,
        rule.channel,
        rule.recipients,
        event.status,
      ]
    );

    await this.sendEscalation(rule.channel, message, rule.recipients);

    return event;
  }

  private async sendEscalation(
    channel: string,
    message: string,
    recipients: string[]
  ): Promise<void> {
    console.log(`[${channel.toUpperCase()}] ${message}`);
    console.log(`Recipients: ${recipients.join(", ")}`);
  }

  async getEscalationHistory(limit: number = 100): Promise<EscalationEvent[]> {
    const result = await this.pool.query(
      `SELECT * FROM escalation_events ORDER BY escalated_at DESC LIMIT $1`,
      [limit]
    );

    return result.rows.map((r) => ({
      event_id: r.event_id,
      signal_type: r.signal_type,
      severity: r.severity,
      message: r.message,
      channel: r.channel,
      recipients: r.recipients || [],
      escalated_at: r.escalated_at,
      acknowledged_at: r.acknowledged_at,
      status: r.status,
    }));
  }

  async acknowledgeEvent(eventId: string): Promise<void> {
    await this.pool.query(
      `UPDATE escalation_events SET status = 'acknowledged', acknowledged_at = NOW() WHERE event_id = $1`,
      [eventId]
    );
  }
}
