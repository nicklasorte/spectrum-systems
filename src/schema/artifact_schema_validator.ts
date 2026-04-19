/**
 * Artifact Schema Validator
 * JSON Schema validation with fail-closed enforcement
 */

import Ajv, { Schema as JSONSchema, ValidateFunction } from "ajv";

export interface SchemaValidationResult {
  artifact_id: string;
  schema_version: string;
  valid: boolean;
  errors?: Array<{
    path: string;
    message: string;
    keyword: string;
  }>;
  warnings?: string[];
  validation_timestamp: string;
}

export interface ArtifactSchema {
  schema_id: string;
  artifact_kind: string;
  schema_version: string;
  json_schema: JSONSchema;
  required_fields: string[];
  created_at: string;
  deprecated: boolean;
  deprecation_reason?: string;
  successor_schema_id?: string;
}

export class SchemaValidator {
  private ajv: Ajv;
  private schemaRegistry: Map<string, ArtifactSchema> = new Map();
  private validatorCache: Map<string, ValidateFunction> = new Map();

  constructor() {
    this.ajv = new Ajv({ strict: true, allErrors: true });
  }

  registerSchema(schema: ArtifactSchema): void {
    if (schema.deprecated && schema.deprecated) {
      console.warn(
        `Registering deprecated schema: ${schema.schema_id}. Successor: ${schema.successor_schema_id}`
      );
    }

    this.schemaRegistry.set(schema.schema_id, schema);
    const validator = this.ajv.compile(schema.json_schema);
    this.validatorCache.set(schema.schema_id, validator);
  }

  getSchema(schemaId: string): ArtifactSchema | undefined {
    return this.schemaRegistry.get(schemaId);
  }

  validateArtifact(
    artifactId: string,
    schemaId: string,
    artifact: Record<string, any>
  ): SchemaValidationResult {
    const schema = this.schemaRegistry.get(schemaId);
    if (!schema) {
      return {
        artifact_id: artifactId,
        schema_version: schemaId,
        valid: false,
        errors: [
          {
            path: "schema",
            message: `Schema not found: ${schemaId}`,
            keyword: "schema_registry",
          },
        ],
        validation_timestamp: new Date().toISOString(),
      };
    }

    if (schema.deprecated) {
      return {
        artifact_id: artifactId,
        schema_version: schemaId,
        valid: false,
        errors: [
          {
            path: "schema",
            message: `Schema is deprecated: ${schema.deprecation_reason}. Use ${schema.successor_schema_id} instead.`,
            keyword: "deprecated_schema",
          },
        ],
        warnings: [`Deprecated schema: ${schema.deprecation_reason}`],
        validation_timestamp: new Date().toISOString(),
      };
    }

    const validator = this.validatorCache.get(schemaId);
    if (!validator) {
      return {
        artifact_id: artifactId,
        schema_version: schemaId,
        valid: false,
        errors: [
          {
            path: "validation",
            message: "Validator compilation failed",
            keyword: "validator_error",
          },
        ],
        validation_timestamp: new Date().toISOString(),
      };
    }

    const valid = validator(artifact);

    if (!valid) {
      return {
        artifact_id: artifactId,
        schema_version: schemaId,
        valid: false,
        errors: (validator.errors || []).map((err) => ({
          path: err.schemaPath || err.instancePath || "root",
          message: err.message || "Unknown validation error",
          keyword: err.keyword || "unknown",
        })),
        validation_timestamp: new Date().toISOString(),
      };
    }

    // Check required fields
    const missingRequired = schema.required_fields.filter(
      (field) => !(field in artifact)
    );
    const warnings = missingRequired.map(
      (field) => `Recommended field missing: ${field}`
    );

    return {
      artifact_id: artifactId,
      schema_version: schemaId,
      valid: true,
      warnings: warnings.length > 0 ? warnings : undefined,
      validation_timestamp: new Date().toISOString(),
    };
  }

  validateBatch(
    schemaId: string,
    artifacts: Array<{ id: string; data: Record<string, any> }>
  ): SchemaValidationResult[] {
    return artifacts.map((artifact) =>
      this.validateArtifact(artifact.id, schemaId, artifact.data)
    );
  }

  listSchemas(): ArtifactSchema[] {
    return Array.from(this.schemaRegistry.values());
  }

  listActiveSchemas(): ArtifactSchema[] {
    return Array.from(this.schemaRegistry.values()).filter(
      (s) => !s.deprecated
    );
  }
}

export function createArtifactSchema(
  schemaId: string,
  artifactKind: string,
  schemaVersion: string,
  jsonSchema: JSONSchema,
  requiredFields: string[] = []
): ArtifactSchema {
  return {
    schema_id: schemaId,
    artifact_kind: artifactKind,
    schema_version: schemaVersion,
    json_schema: jsonSchema,
    required_fields: requiredFields,
    created_at: new Date().toISOString(),
    deprecated: false,
  };
}

export function deprecateSchema(
  schema: ArtifactSchema,
  reason: string,
  successorSchemaId: string
): ArtifactSchema {
  return {
    ...schema,
    deprecated: true,
    deprecation_reason: reason,
    successor_schema_id: successorSchemaId,
  };
}
