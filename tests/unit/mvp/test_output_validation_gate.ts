/**
 * Unit tests for MVP Output Validation Gate
 */

import {
  OutputValidationGate,
  createOutputValidationGate,
} from "../../../src/mvp/output_validation_gate";
import {
  SchemaValidator,
  createArtifactSchema,
} from "../../../src/schema/artifact_schema_validator";
import { generateTraceId, generateSpanId, createTraceparent } from "../../../src/trace/trace_types";
import { v4 as uuidv4 } from "uuid";

describe("Output Validation Gate", () => {
  let gate: OutputValidationGate;
  let validator: SchemaValidator;

  beforeEach(() => {
    validator = new SchemaValidator();
    gate = createOutputValidationGate(validator);

    // Register a test schema
    const schema = createArtifactSchema(
      "test-schema-1",
      "test_output",
      "1.0.0",
      {
        type: "object",
        properties: {
          artifact_id: { type: "string" },
          result: { type: "string" },
          score: { type: "number" },
        },
        required: ["artifact_id", "result"],
      },
      ["artifact_id", "result", "score"]
    );

    validator.registerSchema(schema);
  });

  test("validateOutput passes valid artifact with complete requirements", () => {
    const output = {
      artifact_id: uuidv4(),
      artifact_kind: "test_output",
      schema_id: "test-schema-1",
      data: {
        artifact_id: uuidv4(),
        result: "success",
        score: 0.95,
      },
      trace_context: {
        traceparent: createTraceparent(generateTraceId(), generateSpanId()),
      },
    };

    const result = gate.validateOutput(output);

    expect(result.valid).toBe(true);
    expect(result.artifact).not.toBeNull();
    expect(result.artifact?.created_at).toBeDefined();
  });

  test("validateOutput rejects artifact with missing schema", () => {
    const output = {
      artifact_id: uuidv4(),
      artifact_kind: "test_output",
      schema_id: "nonexistent-schema",
      data: { artifact_id: uuidv4(), result: "success" },
      trace_context: {
        traceparent: createTraceparent(generateTraceId(), generateSpanId()),
      },
    };

    const result = gate.validateOutput(output);

    expect(result.valid).toBe(false);
    expect(result.rejection_reason).toBe("SCHEMA_NOT_FOUND");
    expect(result.artifact).toBeNull();
  });

  test("validateOutput rejects artifact without trace context", () => {
    const output = {
      artifact_id: uuidv4(),
      artifact_kind: "test_output",
      schema_id: "test-schema-1",
      data: { artifact_id: uuidv4(), result: "success" },
      trace_context: { traceparent: "" },
    };

    const result = gate.validateOutput(output);

    expect(result.valid).toBe(false);
    expect(result.rejection_reason).toBe("MISSING_TRACE_CONTEXT");
  });

  test("validateOutput rejects artifact failing schema validation", () => {
    const output = {
      artifact_id: uuidv4(),
      artifact_kind: "test_output",
      schema_id: "test-schema-1",
      data: {
        artifact_id: uuidv4(),
        // result is missing (required field)
        score: "invalid-type",
      },
      trace_context: {
        traceparent: createTraceparent(generateTraceId(), generateSpanId()),
      },
    };

    const result = gate.validateOutput(output);

    expect(result.valid).toBe(false);
    expect(result.rejection_reason).toBe("SCHEMA_VALIDATION_FAILED");
  });

  test("validateOutput rejects artifact with deprecated schema", () => {
    // Deprecate the schema
    const deprecatedSchema = createArtifactSchema(
      "deprecated-schema",
      "test_output",
      "1.0.0",
      { type: "object", properties: {} }
    );
    deprecatedSchema.deprecated = true;
    deprecatedSchema.deprecation_reason = "Use new schema";
    deprecatedSchema.successor_schema_id = "new-schema";

    validator.registerSchema(deprecatedSchema);

    const output = {
      artifact_id: uuidv4(),
      artifact_kind: "test_output",
      schema_id: "deprecated-schema",
      data: {},
      trace_context: {
        traceparent: createTraceparent(generateTraceId(), generateSpanId()),
      },
    };

    const result = gate.validateOutput(output);

    expect(result.valid).toBe(false);
    expect(result.rejection_reason).toBe("SCHEMA_DEPRECATED");
    expect(result.error_details).toContain("new-schema");
  });
});

describe("Output Validation Gate - Batch Operations", () => {
  let gate: OutputValidationGate;
  let validator: SchemaValidator;

  beforeEach(() => {
    validator = new SchemaValidator();
    gate = createOutputValidationGate(validator);

    const schema = createArtifactSchema(
      "batch-schema",
      "test_output",
      "1.0.0",
      {
        type: "object",
        properties: {
          id: { type: "string" },
          status: { type: "string" },
        },
        required: ["id"],
      }
    );

    validator.registerSchema(schema);
  });

  test("validateBatch validates multiple outputs", () => {
    const outputs = [
      {
        artifact_id: uuidv4(),
        artifact_kind: "test_output",
        schema_id: "batch-schema",
        data: { id: "1", status: "ok" },
        trace_context: {
          traceparent: createTraceparent(generateTraceId(), generateSpanId()),
        },
      },
      {
        artifact_id: uuidv4(),
        artifact_kind: "test_output",
        schema_id: "batch-schema",
        data: { id: "2", status: "ok" },
        trace_context: {
          traceparent: createTraceparent(generateTraceId(), generateSpanId()),
        },
      },
      {
        artifact_id: uuidv4(),
        artifact_kind: "test_output",
        schema_id: "batch-schema",
        data: { status: "ok" }, // missing id
        trace_context: {
          traceparent: createTraceparent(generateTraceId(), generateSpanId()),
        },
      },
    ];

    const results = gate.validateBatch(outputs);

    expect(results).toHaveLength(3);
    expect(results[0].valid).toBe(true);
    expect(results[1].valid).toBe(true);
    expect(results[2].valid).toBe(false);
  });

  test("getValidationStats reports batch statistics", () => {
    const outputs = [
      {
        artifact_id: uuidv4(),
        artifact_kind: "test_output",
        schema_id: "batch-schema",
        data: { id: "1" },
        trace_context: {
          traceparent: createTraceparent(generateTraceId(), generateSpanId()),
        },
      },
      {
        artifact_id: uuidv4(),
        artifact_kind: "test_output",
        schema_id: "batch-schema",
        data: { id: "2" },
        trace_context: {
          traceparent: createTraceparent(generateTraceId(), generateSpanId()),
        },
      },
      {
        artifact_id: uuidv4(),
        artifact_kind: "test_output",
        schema_id: "nonexistent",
        data: { id: "3" },
        trace_context: {
          traceparent: createTraceparent(generateTraceId(), generateSpanId()),
        },
      },
    ];

    const results = gate.validateBatch(outputs);
    const stats = gate.getValidationStats(results);

    expect(stats.total).toBe(3);
    expect(stats.valid).toBe(2);
    expect(stats.invalid).toBe(1);
    expect(stats.pass_rate).toBe(66.67);
    expect(stats.failure_reasons["SCHEMA_NOT_FOUND"]).toBe(1);
  });
});

describe("Output Validation Gate - Fail-Closed Enforcement", () => {
  let gate: OutputValidationGate;
  let validator: SchemaValidator;

  beforeEach(() => {
    validator = new SchemaValidator();
    gate = createOutputValidationGate(validator);
  });

  test("Fail-closed: no artifact returned on any failure", () => {
    const output = {
      artifact_id: uuidv4(),
      artifact_kind: "test_output",
      schema_id: "missing-schema",
      data: {},
      trace_context: { traceparent: "" },
    };

    const result = gate.validateOutput(output);

    expect(result.valid).toBe(false);
    expect(result.artifact).toBeNull();
    expect(result.rejection_reason).toBeDefined();
  });

  test("Fail-closed: batch with any failures returns mixed results", () => {
    const schema = createArtifactSchema(
      "test",
      "type",
      "1.0.0",
      { type: "object", properties: { id: { type: "string" } } }
    );
    validator.registerSchema(schema);

    const outputs = [
      {
        artifact_id: uuidv4(),
        artifact_kind: "test_output",
        schema_id: "test",
        data: { id: "ok" },
        trace_context: {
          traceparent: createTraceparent(generateTraceId(), generateSpanId()),
        },
      },
      {
        artifact_id: uuidv4(),
        artifact_kind: "test_output",
        schema_id: "test",
        data: { id: 123 }, // invalid type
        trace_context: {
          traceparent: createTraceparent(generateTraceId(), generateSpanId()),
        },
      },
    ];

    const results = gate.validateBatch(outputs);

    expect(results[0].artifact).not.toBeNull();
    expect(results[1].artifact).toBeNull();
  });
});
