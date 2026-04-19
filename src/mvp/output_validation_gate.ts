/**
 * MVP Output Validation Gate (Cluster E)
 * Fail-closed enforcement: validate at artifact creation, reject invalid artifacts
 */

import { SchemaValidator, SchemaValidationResult } from "../schema/artifact_schema_validator";
import { TraceContext } from "../trace/trace_types";

export interface MVPOutput {
  artifact_id: string;
  artifact_kind: string;
  schema_id: string;
  data: Record<string, any>;
  trace_context: TraceContext;
  created_at?: string;
}

export interface ValidatedMVPOutput {
  valid: boolean;
  artifact: MVPOutput | null;
  validation_result: SchemaValidationResult;
  rejection_reason?: string;
  error_details?: string;
}

export class OutputValidationGate {
  private schemaValidator: SchemaValidator;

  constructor(schemaValidator: SchemaValidator) {
    this.schemaValidator = schemaValidator;
  }

  validateOutput(
    mvpOutput: Omit<MVPOutput, "created_at">
  ): ValidatedMVPOutput {
    // Step 1: Check schema exists
    const schema = this.schemaValidator.getSchema(mvpOutput.schema_id);
    if (!schema) {
      return {
        valid: false,
        artifact: null,
        validation_result: {
          artifact_id: mvpOutput.artifact_id,
          schema_version: mvpOutput.schema_id,
          valid: false,
          errors: [
            {
              path: "schema",
              message: `Schema not found: ${mvpOutput.schema_id}`,
              keyword: "schema_not_found",
            },
          ],
          validation_timestamp: new Date().toISOString(),
        },
        rejection_reason: "SCHEMA_NOT_FOUND",
        error_details: `Artifact kind ${mvpOutput.artifact_kind} requires schema ${mvpOutput.schema_id}`,
      };
    }

    // Step 2: Check schema is not deprecated
    if (schema.deprecated) {
      return {
        valid: false,
        artifact: null,
        validation_result: {
          artifact_id: mvpOutput.artifact_id,
          schema_version: mvpOutput.schema_id,
          valid: false,
          errors: [
            {
              path: "schema",
              message: `Schema is deprecated: ${schema.deprecation_reason}`,
              keyword: "deprecated_schema",
            },
          ],
          validation_timestamp: new Date().toISOString(),
        },
        rejection_reason: "SCHEMA_DEPRECATED",
        error_details: `Use schema ${schema.successor_schema_id} instead`,
      };
    }

    // Step 3: Validate artifact against schema
    const validationResult = this.schemaValidator.validateArtifact(
      mvpOutput.artifact_id,
      mvpOutput.schema_id,
      mvpOutput.data
    );

    if (!validationResult.valid) {
      return {
        valid: false,
        artifact: null,
        validation_result: validationResult,
        rejection_reason: "SCHEMA_VALIDATION_FAILED",
        error_details: validationResult.errors
          ?.map((e) => `${e.path}: ${e.message}`)
          .join("; "),
      };
    }

    // Step 4: Check trace context
    if (!mvpOutput.trace_context || !mvpOutput.trace_context.traceparent) {
      return {
        valid: false,
        artifact: null,
        validation_result: validationResult,
        rejection_reason: "MISSING_TRACE_CONTEXT",
        error_details: "Artifact must be created within active trace context",
      };
    }

    // All checks passed
    const validatedArtifact: MVPOutput = {
      ...mvpOutput,
      created_at: new Date().toISOString(),
    };

    return {
      valid: true,
      artifact: validatedArtifact,
      validation_result: validationResult,
    };
  }

  validateBatch(
    outputs: Array<Omit<MVPOutput, "created_at">>
  ): ValidatedMVPOutput[] {
    return outputs.map((output) => this.validateOutput(output));
  }

  getValidationStats(results: ValidatedMVPOutput[]): {
    total: number;
    valid: number;
    invalid: number;
    pass_rate: number;
    failure_reasons: Record<string, number>;
  } {
    const failureReasons: Record<string, number> = {};

    for (const result of results) {
      if (!result.valid && result.rejection_reason) {
        failureReasons[result.rejection_reason] =
          (failureReasons[result.rejection_reason] || 0) + 1;
      }
    }

    const valid = results.filter((r) => r.valid).length;
    const invalid = results.length - valid;

    return {
      total: results.length,
      valid,
      invalid,
      pass_rate: results.length > 0 ? (valid / results.length) * 100 : 0,
      failure_reasons: failureReasons,
    };
  }
}

export function createOutputValidationGate(
  schemaValidator: SchemaValidator
): OutputValidationGate {
  return new OutputValidationGate(schemaValidator);
}
