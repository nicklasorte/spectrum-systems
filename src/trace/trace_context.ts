/**
 * W3C Trace Context Propagation
 * Ensures causal visibility across all steps in the governance pipeline
 */

import {
  TraceContext,
  TraceSpan,
  generateTraceId,
  generateSpanId,
  createTraceparent,
  parseTraceparent,
} from "./trace_types";

let currentContext: TraceContext | null = null;
let currentSpanId: string | null = null;
const spans: Map<string, TraceSpan[]> = new Map();

export function initializeTraceContext(
  traceId?: string,
  tracestate?: string
): TraceContext {
  const actualTraceId = traceId || generateTraceId();
  const spanId = generateSpanId();

  currentContext = {
    traceparent: createTraceparent(actualTraceId, spanId),
    tracestate,
  };
  currentSpanId = spanId;

  if (!spans.has(actualTraceId)) {
    spans.set(actualTraceId, []);
  }

  return currentContext;
}

export function propagateTraceContext(
  parentContext: TraceContext
): TraceContext {
  const parsed = parseTraceparent(parentContext.traceparent);
  if (!parsed) {
    throw new Error(`Invalid traceparent format: ${parentContext.traceparent}`);
  }

  const newSpanId = generateSpanId();
  const newContext: TraceContext = {
    traceparent: `00-${parsed.traceId}-${newSpanId}-${parsed.sampled ? "01" : "00"}`,
    tracestate: parentContext.tracestate,
  };

  currentContext = newContext;
  currentSpanId = newSpanId;

  if (!spans.has(parsed.traceId)) {
    spans.set(parsed.traceId, []);
  }

  return newContext;
}

export function getCurrentTraceContext(): TraceContext | null {
  return currentContext;
}

export function addSpan(
  span: Omit<TraceSpan, "trace_id" | "span_id">,
  traceId: string
): TraceSpan {
  const parsed = parseTraceparent(currentContext?.traceparent || "");
  if (!parsed) {
    throw new Error("No active trace context");
  }

  const fullSpan: TraceSpan = {
    ...span,
    trace_id: traceId,
    span_id: currentSpanId || generateSpanId(),
  };

  const traceSpans = spans.get(traceId) || [];
  traceSpans.push(fullSpan);
  spans.set(traceId, traceSpans);

  return fullSpan;
}

export function getTraceSpans(traceId: string): TraceSpan[] {
  return spans.get(traceId) || [];
}

export function validateTraceContextChain(traceId: string): {
  valid: boolean;
  gaps: number;
  reason?: string;
} {
  const traceSpans = spans.get(traceId);
  if (!traceSpans || traceSpans.length === 0) {
    return { valid: false, gaps: 0, reason: "No spans found for trace" };
  }

  let gaps = 0;
  for (let i = 1; i < traceSpans.length; i++) {
    if (!traceSpans[i].parent_span_id) {
      gaps++;
    }
  }

  return {
    valid: gaps === 0,
    gaps,
    reason: gaps > 0 ? `Found ${gaps} spans with missing parent span IDs` : undefined,
  };
}

export function clearTraceContext(): void {
  currentContext = null;
  currentSpanId = null;
  spans.clear();
}

export function exportTraceSpans(traceId: string): string {
  const traceSpans = spans.get(traceId) || [];
  return JSON.stringify(traceSpans, null, 2);
}
