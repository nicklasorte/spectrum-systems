/**
 * Enhanced escalation with context
 * Addresses red team finding on escalation context
 */

export interface EnhancedEscalationEvent {
  event_id: string;
  signal_type: string;
  severity: string;
  artifact_id: string;
  trace_id: string;
  message: string;
  context_url: string;
  historical_trend?: string;
  channel: string;
  recipients: string[];
  escalated_at: string;
  acknowledged_at?: string;
  status: "sent" | "acknowledged" | "failed";
}

export function buildEscalationContext(
  signalType: string,
  artifactId: string,
  traceId: string,
  currentValue: number,
  baseline: number
): string {
  const shift = ((currentValue - baseline) / baseline) * 100;
  return `
Signal: ${signalType}
Artifact: ${artifactId}
Trace: ${traceId}
Current: ${currentValue}
Baseline: ${baseline}
Shift: ${shift.toFixed(1)}%
Investigate: /dashboard/artifacts/${artifactId}?trace=${traceId}
  `;
}

export function formatEscalationMessage(
  severity: string,
  signalType: string,
  context: string,
  artifactId: string
): string {
  const levelEmoji: Record<string, string> = {
    warn: "⚠️",
    freeze: "🔒",
    block: "🛑",
  };

  const emoji = levelEmoji[severity] || "📢";

  return `${emoji} ${severity.toUpperCase()}: ${signalType}
Artifact: ${artifactId}
${context}`;
}
