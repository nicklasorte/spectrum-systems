import { ValidationError } from "./types";

export function validateBeforeStore(artifact: unknown): {
  valid: boolean;
  errors?: ValidationError[];
} {
  // Check that artifact is an object
  if (typeof artifact !== "object" || !artifact) {
    return {
      valid: false,
      errors: [
        {
          field: "root",
          message: "Artifact must be an object",
          code: "schema_violation",
        },
      ],
    };
  }

  const artifact_obj = artifact as Record<string, unknown>;

  // Must have required fields
  if (!artifact_obj.artifact_kind) {
    return {
      valid: false,
      errors: [
        {
          field: "artifact_kind",
          message: "Required field missing",
          code: "missing_required_field",
        },
      ],
    };
  }

  if (!artifact_obj.artifact_id) {
    return {
      valid: false,
      errors: [
        {
          field: "artifact_id",
          message: "Required field missing",
          code: "missing_required_field",
        },
      ],
    };
  }

  // Must be a string
  if (typeof artifact_obj.artifact_kind !== "string") {
    return {
      valid: false,
      errors: [
        {
          field: "artifact_kind",
          message: "artifact_kind must be a string",
          code: "schema_violation",
        },
      ],
    };
  }

  if (typeof artifact_obj.artifact_id !== "string") {
    return {
      valid: false,
      errors: [
        {
          field: "artifact_id",
          message: "artifact_id must be a string",
          code: "schema_violation",
        },
      ],
    };
  }

  return { valid: true };
}

export function computeContentHash(artifact: unknown): string {
  // Simple SHA256 hash of artifact content
  const crypto = require("crypto");
  const content = JSON.stringify(artifact);
  const hash = crypto.createHash("sha256").update(content).digest("hex");
  return `sha256:${hash}`;
}

export function validateProvenance(provenance: Record<string, unknown>): boolean {
  // Ensure provenance has required fields
  return !!(
    provenance.producedBy &&
    provenance.inputArtifactIds &&
    provenance.executionFingerprint &&
    provenance.traceId
  );
}
