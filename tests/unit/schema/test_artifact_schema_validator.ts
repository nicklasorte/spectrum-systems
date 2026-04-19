/**
 * Unit tests for Artifact Schema Validator
 */

import {
  SchemaValidator,
  createArtifactSchema,
  deprecateSchema,
} from "../../../src/schema/artifact_schema_validator";

describe("Schema Validator - Registration & Retrieval", () => {
  let validator: SchemaValidator;

  beforeEach(() => {
    validator = new SchemaValidator();
  });

  test("registerSchema adds schema to registry", () => {
    const schema = createArtifactSchema(
      "schema-1",
      "artifact_type_1",
      "1.0.0",
      {
        type: "object",
        properties: {
          id: { type: "string" },
          name: { type: "string" },
        },
        required: ["id", "name"],
      },
      ["id", "name"]
    );

    validator.registerSchema(schema);
    const retrieved = validator.getSchema("schema-1");

    expect(retrieved).toEqual(schema);
  });

  test("getSchema returns undefined for unknown schema", () => {
    const retrieved = validator.getSchema("nonexistent");
    expect(retrieved).toBeUndefined();
  });

  test("listSchemas returns all registered schemas", () => {
    const schema1 = createArtifactSchema(
      "schema-1",
      "type1",
      "1.0.0",
      { type: "object", properties: {} }
    );
    const schema2 = createArtifactSchema(
      "schema-2",
      "type2",
      "1.0.0",
      { type: "object", properties: {} }
    );

    validator.registerSchema(schema1);
    validator.registerSchema(schema2);

    const schemas = validator.listSchemas();
    expect(schemas).toHaveLength(2);
  });

  test("listActiveSchemas excludes deprecated schemas", () => {
    const schema1 = createArtifactSchema(
      "schema-1",
      "type1",
      "1.0.0",
      { type: "object", properties: {} }
    );
    const schema2 = createArtifactSchema(
      "schema-2",
      "type2",
      "1.0.0",
      { type: "object", properties: {} }
    );
    const deprecated = deprecateSchema(schema1, "Old format", "schema-2");

    validator.registerSchema(deprecated);
    validator.registerSchema(schema2);

    const active = validator.listActiveSchemas();
    expect(active).toHaveLength(1);
    expect(active[0].schema_id).toBe("schema-2");
  });
});

describe("Schema Validator - Validation", () => {
  let validator: SchemaValidator;

  beforeEach(() => {
    validator = new SchemaValidator();
  });

  test("validateArtifact passes valid artifact", () => {
    const schema = createArtifactSchema(
      "schema-1",
      "test_artifact",
      "1.0.0",
      {
        type: "object",
        properties: {
          id: { type: "string" },
          value: { type: "number" },
        },
        required: ["id", "value"],
      },
      ["id", "value"]
    );

    validator.registerSchema(schema);

    const result = validator.validateArtifact(
      "artifact-1",
      "schema-1",
      {
        id: "test-123",
        value: 42,
      }
    );

    expect(result.valid).toBe(true);
    expect(result.errors).toBeUndefined();
  });

  test("validateArtifact rejects missing required field", () => {
    const schema = createArtifactSchema(
      "schema-1",
      "test_artifact",
      "1.0.0",
      {
        type: "object",
        properties: {
          id: { type: "string" },
          value: { type: "number" },
        },
        required: ["id", "value"],
      },
      ["id", "value"]
    );

    validator.registerSchema(schema);

    const result = validator.validateArtifact(
      "artifact-1",
      "schema-1",
      {
        id: "test-123",
        // value is missing
      }
    );

    expect(result.valid).toBe(false);
    expect(result.errors).toBeDefined();
  });

  test("validateArtifact rejects wrong type", () => {
    const schema = createArtifactSchema(
      "schema-1",
      "test_artifact",
      "1.0.0",
      {
        type: "object",
        properties: {
          id: { type: "string" },
          value: { type: "number" },
        },
        required: ["id", "value"],
      }
    );

    validator.registerSchema(schema);

    const result = validator.validateArtifact(
      "artifact-1",
      "schema-1",
      {
        id: "test-123",
        value: "not-a-number", // wrong type
      }
    );

    expect(result.valid).toBe(false);
    expect(result.errors).toBeDefined();
  });

  test("validateArtifact rejects unregistered schema", () => {
    const result = validator.validateArtifact(
      "artifact-1",
      "unknown-schema",
      { test: "data" }
    );

    expect(result.valid).toBe(false);
    expect(result.errors?.some((e) => e.keyword === "schema_registry")).toBe(
      true
    );
  });

  test("validateArtifact rejects deprecated schema", () => {
    const schema = createArtifactSchema(
      "schema-1",
      "test_artifact",
      "1.0.0",
      { type: "object", properties: {} }
    );
    const deprecated = deprecateSchema(schema, "Use schema-2", "schema-2");
    validator.registerSchema(deprecated);

    const result = validator.validateArtifact(
      "artifact-1",
      "schema-1",
      {}
    );

    expect(result.valid).toBe(false);
    expect(
      result.errors?.some((e) => e.keyword === "deprecated_schema")
    ).toBe(true);
  });

  test("validateArtifact warns about missing recommended fields", () => {
    const schema = createArtifactSchema(
      "schema-1",
      "test_artifact",
      "1.0.0",
      {
        type: "object",
        properties: {
          id: { type: "string" },
          created_at: { type: "string" },
        },
        required: ["id"],
      },
      ["id", "created_at"]
    );

    validator.registerSchema(schema);

    const result = validator.validateArtifact(
      "artifact-1",
      "schema-1",
      {
        id: "test-123",
        // created_at is missing but recommended
      }
    );

    expect(result.valid).toBe(true);
    expect(result.warnings).toBeDefined();
    expect(result.warnings?.some((w) => w.includes("created_at"))).toBe(true);
  });
});

describe("Schema Validator - Batch Validation", () => {
  let validator: SchemaValidator;

  beforeEach(() => {
    validator = new SchemaValidator();

    const schema = createArtifactSchema(
      "schema-1",
      "test_artifact",
      "1.0.0",
      {
        type: "object",
        properties: {
          id: { type: "string" },
          value: { type: "number" },
        },
        required: ["id", "value"],
      }
    );

    validator.registerSchema(schema);
  });

  test("validateBatch validates multiple artifacts", () => {
    const results = validator.validateBatch("schema-1", [
      { id: "a1", data: { id: "test1", value: 10 } },
      { id: "a2", data: { id: "test2", value: 20 } },
      { id: "a3", data: { id: "test3", value: "invalid" } },
    ]);

    expect(results).toHaveLength(3);
    expect(results[0].valid).toBe(true);
    expect(results[1].valid).toBe(true);
    expect(results[2].valid).toBe(false);
  });
});

describe("Schema - Creation & Deprecation", () => {
  test("createArtifactSchema creates valid schema object", () => {
    const schema = createArtifactSchema(
      "test-schema",
      "test_artifact",
      "1.0.0",
      { type: "object", properties: {} },
      ["field1", "field2"]
    );

    expect(schema.schema_id).toBe("test-schema");
    expect(schema.artifact_kind).toBe("test_artifact");
    expect(schema.schema_version).toBe("1.0.0");
    expect(schema.deprecated).toBe(false);
    expect(schema.required_fields).toEqual(["field1", "field2"]);
  });

  test("deprecateSchema marks schema as deprecated", () => {
    const original = createArtifactSchema(
      "schema-1",
      "type1",
      "1.0.0",
      { type: "object", properties: {} }
    );

    const deprecated = deprecateSchema(
      original,
      "Use new format",
      "schema-2"
    );

    expect(deprecated.deprecated).toBe(true);
    expect(deprecated.deprecation_reason).toBe("Use new format");
    expect(deprecated.successor_schema_id).toBe("schema-2");
  });
});
