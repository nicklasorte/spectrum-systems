/**
 * W3C Trace Context Types
 * OTEL-compatible distributed tracing for governance artifacts
 */

export interface TraceContext {
  traceparent: string; // version-trace_id-parent_id-trace_flags
  tracestate?: string; // vendor-specific trace state
}

export interface TraceSpan {
  trace_id: string;
  parent_span_id: string;
  span_id: string;
  span_name: string;
  start_time: string;
  end_time?: string;
  status: "unset" | "ok" | "error";
  attributes?: Record<string, string | number | boolean>;
}

export interface ArtifactTrace {
  trace_id: string;
  artifact_id: string;
  artifact_kind: string;
  created_at: string;
  spans: TraceSpan[];
  root_cause_path?: string[];
}

export function generateTraceId(): string {
  const randomBytes = Array.from({ length: 8 }, () =>
    Math.floor(Math.random() * 256)
      .toString(16)
      .padStart(2, "0")
  ).join("");
  return randomBytes;
}

export function generateSpanId(): string {
  const randomBytes = Array.from({ length: 4 }, () =>
    Math.floor(Math.random() * 256)
      .toString(16)
      .padStart(2, "0")
  ).join("");
  return randomBytes;
}

export function createTraceparent(
  traceId: string,
  parentSpanId: string,
  traceSampled = true
): string {
  const version = "00";
  const flags = traceSampled ? "01" : "00";
  return `${version}-${traceId}-${parentSpanId}-${flags}`;
}

export function parseTraceparent(traceparent: string): {
  traceId: string;
  parentSpanId: string;
  sampled: boolean;
} | null {
  const parts = traceparent.split("-");
  if (parts.length !== 4 || parts[0] !== "00") return null;
  return {
    traceId: parts[1],
    parentSpanId: parts[2],
    sampled: parts[3] === "01",
  };
}

export function validateTraceId(traceId: string): boolean {
  return /^[a-f0-9]{32}$/.test(traceId);
}

export function validateSpanId(spanId: string): boolean {
  return /^[a-f0-9]{16}$/.test(spanId);
}
