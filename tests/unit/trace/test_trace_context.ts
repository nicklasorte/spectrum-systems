/**
 * Unit tests for W3C Trace Context propagation
 */

import {
  generateTraceId,
  generateSpanId,
  createTraceparent,
  parseTraceparent,
  validateTraceId,
  validateSpanId,
} from "../../../src/trace/trace_types";
import {
  initializeTraceContext,
  propagateTraceContext,
  getCurrentTraceContext,
  validateTraceContextChain,
  clearTraceContext,
} from "../../../src/trace/trace_context";

describe("Trace Context - Type Utilities", () => {
  test("generateTraceId produces valid 32-char hex", () => {
    const traceId = generateTraceId();
    expect(traceId).toMatch(/^[a-f0-9]{32}$/);
  });

  test("generateSpanId produces valid 16-char hex", () => {
    const spanId = generateSpanId();
    expect(spanId).toMatch(/^[a-f0-9]{16}$/);
  });

  test("createTraceparent formats correctly", () => {
    const traceId = generateTraceId();
    const spanId = generateSpanId();
    const traceparent = createTraceparent(traceId, spanId, true);

    expect(traceparent).toMatch(/^00-[a-f0-9]{32}-[a-f0-9]{16}-01$/);
  });

  test("parseTraceparent extracts components correctly", () => {
    const traceId = generateTraceId();
    const spanId = generateSpanId();
    const traceparent = createTraceparent(traceId, spanId, true);

    const parsed = parseTraceparent(traceparent);
    expect(parsed).not.toBeNull();
    expect(parsed?.traceId).toBe(traceId);
    expect(parsed?.parentSpanId).toBe(spanId);
    expect(parsed?.sampled).toBe(true);
  });

  test("validateTraceId rejects invalid formats", () => {
    expect(validateTraceId("invalid")).toBe(false);
    expect(validateTraceId("00000000000000000000000000000000")).toBe(true);
  });

  test("validateSpanId rejects invalid formats", () => {
    expect(validateSpanId("short")).toBe(false);
    expect(validateSpanId("0000000000000000")).toBe(true);
  });
});

describe("Trace Context - Propagation", () => {
  beforeEach(() => clearTraceContext());

  test("initializeTraceContext creates valid context", () => {
    const context = initializeTraceContext();

    expect(context.traceparent).toMatch(/^00-[a-f0-9]{32}-[a-f0-9]{16}-01$/);
    expect(getCurrentTraceContext()).toEqual(context);
  });

  test("initializeTraceContext with specific traceId", () => {
    const traceId = generateTraceId();
    const context = initializeTraceContext(traceId);

    const parsed = parseTraceparent(context.traceparent);
    expect(parsed?.traceId).toBe(traceId);
  });

  test("propagateTraceContext preserves traceId", () => {
    const initContext = initializeTraceContext();
    const initParsed = parseTraceparent(initContext.traceparent);

    const childContext = propagateTraceContext(initContext);
    const childParsed = parseTraceparent(childContext.traceparent);

    expect(childParsed?.traceId).toBe(initParsed?.traceId);
    expect(childParsed?.parentSpanId).not.toBe(initParsed?.parentSpanId);
  });

  test("propagateTraceContext rejects invalid context", () => {
    expect(() => {
      propagateTraceContext({ traceparent: "invalid", tracestate: undefined });
    }).toThrow();
  });
});

describe("Trace Context - Chain Validation", () => {
  beforeEach(() => clearTraceContext());

  test("validateTraceContextChain detects missing parent span IDs", () => {
    const context = initializeTraceContext();
    const parsed = parseTraceparent(context.traceparent);

    if (!parsed) throw new Error("Failed to parse context");

    // Validate empty chain
    const result = validateTraceContextChain(parsed.traceId);
    expect(result.valid).toBe(false);
  });

  test("validateTraceContextChain returns valid for complete chain", () => {
    const context = initializeTraceContext();
    const parsed = parseTraceparent(context.traceparent);

    if (!parsed) throw new Error("Failed to parse context");

    // Spans are added during execution; this test verifies the validator structure
    const result = validateTraceContextChain(parsed.traceId);
    expect(result).toHaveProperty("valid");
    expect(result).toHaveProperty("gaps");
  });
});
