/**
 * Unit tests for Pre-Promotion Checks
 */

import {
  checkTraceContextValidity,
  checkProvenanceCompleteness,
  runPrePromotionChecks,
} from "../../../src/promotion/pre_promotion_checks";
import {
  createProvenanceChain,
  ProvenanceChain,
} from "../../../src/provenance/chain_validator";
import { createTraceparent, generateTraceId, generateSpanId } from "../../../src/trace/trace_types";
import { v4 as uuidv4 } from "uuid";

describe("Pre-Promotion Checks - Trace Validity", () => {
  test("checkTraceContextValidity rejects null context", () => {
    const { valid, failures } = checkTraceContextValidity(null);

    expect(valid).toBe(false);
    expect(failures).toHaveLength(1);
    expect(failures[0].check_name).toBe("trace_context_exists");
    expect(failures[0].severity).toBe("critical");
  });

  test("checkTraceContextValidity rejects missing traceparent", () => {
    const { valid, failures } = checkTraceContextValidity({
      traceparent: "",
      tracestate: undefined,
    });

    expect(valid).toBe(false);
    expect(failures.some((f) => f.check_name === "traceparent_format")).toBe(true);
  });

  test("checkTraceContextValidity rejects invalid trace_id format", () => {
    const { valid, failures } = checkTraceContextValidity({
      traceparent: "00-invalid-0000000000000000-01",
      tracestate: undefined,
    });

    expect(valid).toBe(false);
    expect(failures.some((f) => f.check_name === "trace_id_format")).toBe(true);
  });

  test("checkTraceContextValidity rejects invalid span_id format", () => {
    const { valid, failures } = checkTraceContextValidity({
      traceparent: `00-${generateTraceId()}-invalid-01`,
      tracestate: undefined,
    });

    expect(valid).toBe(false);
    expect(failures.some((f) => f.check_name === "parent_span_id_format")).toBe(true);
  });

  test("checkTraceContextValidity accepts valid context", () => {
    const { valid, failures } = checkTraceContextValidity({
      traceparent: `00-${generateTraceId()}-${generateSpanId()}-01`,
      tracestate: undefined,
    });

    expect(valid).toBe(true);
    expect(failures.filter((f) => f.severity === "critical")).toHaveLength(0);
  });
});

describe("Pre-Promotion Checks - Provenance Completeness", () => {
  test("checkProvenanceCompleteness rejects null chain", () => {
    const { complete, failures } = checkProvenanceCompleteness(null);

    expect(complete).toBe(false);
    expect(failures).toHaveLength(1);
    expect(failures[0].check_name).toBe("provenance_chain_exists");
  });

  test("checkProvenanceCompleteness rejects missing inputs", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      [], // missing inputs
      {
        code_version: "abc123",
        model_version: "model-v1.0",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      []
    );

    const { complete, failures } = checkProvenanceCompleteness(chain);

    expect(complete).toBe(false);
    expect(failures.some((f) => f.check_name === "provenance_inputs")).toBe(true);
  });

  test("checkProvenanceCompleteness rejects missing code version", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "", // missing
        model_version: "model-v1.0",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      []
    );

    const { complete, failures } = checkProvenanceCompleteness(chain);

    expect(complete).toBe(false);
    expect(failures.some((f) => f.check_name === "provenance_code_version")).toBe(true);
  });

  test("checkProvenanceCompleteness rejects missing model version", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "abc123",
        model_version: "", // missing
        runtime_version: "1.0.0",
      },
      ["output-1"],
      []
    );

    const { complete, failures } = checkProvenanceCompleteness(chain);

    expect(complete).toBe(false);
    expect(failures.some((f) => f.check_name === "provenance_model_version")).toBe(true);
  });

  test("checkProvenanceCompleteness rejects missing outputs", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "abc123",
        model_version: "model-v1.0",
        runtime_version: "1.0.0",
      },
      [], // missing outputs
      []
    );

    const { complete, failures } = checkProvenanceCompleteness(chain);

    expect(complete).toBe(false);
    expect(failures.some((f) => f.check_name === "provenance_outputs")).toBe(true);
  });

  test("checkProvenanceCompleteness accepts complete chain", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "abc123",
        model_version: "model-v1.0",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      [
        {
          link_id: uuidv4(),
          from_artifact_id: "input-1",
          to_artifact_id: "output-1",
          from_kind: "input",
          to_kind: "output",
          relationship: "inputs_to",
          timestamp: new Date().toISOString(),
          evidence: "test",
        },
        {
          link_id: uuidv4(),
          from_artifact_id: "code-1",
          to_artifact_id: "output-1",
          from_kind: "code",
          to_kind: "output",
          relationship: "executed_by",
          timestamp: new Date().toISOString(),
          evidence: "test",
        },
        {
          link_id: uuidv4(),
          from_artifact_id: "output-1",
          to_artifact_id: "output-1",
          from_kind: "output",
          to_kind: "output",
          relationship: "produced_by",
          timestamp: new Date().toISOString(),
          evidence: "test",
        },
      ]
    );

    const { complete, failures } = checkProvenanceCompleteness(chain);

    expect(complete).toBe(true);
    expect(failures.filter((f) => f.severity === "critical")).toHaveLength(0);
  });
});

describe("Pre-Promotion Checks - Full Check Run", () => {
  test("runPrePromotionChecks blocks promotion with missing trace", () => {
    const result = runPrePromotionChecks(
      uuidv4(),
      uuidv4(),
      null, // no trace context
      null // no provenance
    );

    expect(result.promotion_ready).toBe(false);
    expect(result.checks_passed).toBe(false);
    expect(result.failed_checks.length).toBeGreaterThan(0);
  });

  test("runPrePromotionChecks blocks promotion with incomplete provenance", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      [], // missing inputs
      {
        code_version: "abc123",
        model_version: "model-v1.0",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      []
    );

    const result = runPrePromotionChecks(
      uuidv4(),
      uuidv4(),
      {
        traceparent: `00-${generateTraceId()}-${generateSpanId()}-01`,
        tracestate: undefined,
      },
      chain
    );

    expect(result.promotion_ready).toBe(false);
    expect(result.failed_checks.some((f) => f.check_name === "provenance_inputs")).toBe(true);
  });

  test("runPrePromotionChecks approves promotion with complete checks", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "abc123",
        model_version: "model-v1.0",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      [
        {
          link_id: uuidv4(),
          from_artifact_id: "input-1",
          to_artifact_id: "output-1",
          from_kind: "input",
          to_kind: "output",
          relationship: "inputs_to",
          timestamp: new Date().toISOString(),
          evidence: "test",
        },
        {
          link_id: uuidv4(),
          from_artifact_id: "code-1",
          to_artifact_id: "output-1",
          from_kind: "code",
          to_kind: "output",
          relationship: "executed_by",
          timestamp: new Date().toISOString(),
          evidence: "test",
        },
        {
          link_id: uuidv4(),
          from_artifact_id: "output-1",
          to_artifact_id: "output-1",
          from_kind: "output",
          to_kind: "output",
          relationship: "produced_by",
          timestamp: new Date().toISOString(),
          evidence: "test",
        },
      ]
    );

    const result = runPrePromotionChecks(
      uuidv4(),
      uuidv4(),
      {
        traceparent: `00-${generateTraceId()}-${generateSpanId()}-01`,
        tracestate: undefined,
      },
      chain
    );

    expect(result.promotion_ready).toBe(true);
    expect(result.checks_passed).toBe(true);
    expect(result.failed_checks).toHaveLength(0);
  });
});
