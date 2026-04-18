import * as fs from "fs";
import * as path from "path";
import Ajv from "ajv";
import type {
  TranscriptArtifact,
  ContextBundle,
  AgentExecutionTrace,
  EvalCase,
  EvalResult,
  EvalSummary,
  ControlDecisionArtifact,
  PQXExecutionRecord,
  FailureArtifact,
  AnyArtifact,
} from "./index";

// Initialize JSON Schema validator
const ajv = new Ajv();

// Load schemas from current directory
const commonSchema = JSON.parse(
  fs.readFileSync(path.join(__dirname, "common.schema.json"), "utf-8")
);

const schemas: Record<string, unknown> = {
  "common.schema.json": commonSchema,
};

const artifactSchemas = [
  "transcript_artifact",
  "context_bundle",
  "agent_execution_trace",
  "eval_case",
  "eval_result",
  "eval_summary",
  "control_decision",
  "pqx_execution_record",
  "failure_artifact",
];

artifactSchemas.forEach((name) => {
  const schema = JSON.parse(
    fs.readFileSync(path.join(__dirname, "artifacts", `${name}.schema.json`), "utf-8")
  );
  schemas[`artifacts/${name}.schema.json`] = schema;
});

// Compile validators
export const validators = {
  transcript_artifact: ajv.compile(schemas["artifacts/transcript_artifact.schema.json"] as any),
  context_bundle: ajv.compile(schemas["artifacts/context_bundle.schema.json"] as any),
  agent_execution_trace: ajv.compile(
    schemas["artifacts/agent_execution_trace.schema.json"] as any
  ),
  eval_case: ajv.compile(schemas["artifacts/eval_case.schema.json"] as any),
  eval_result: ajv.compile(schemas["artifacts/eval_result.schema.json"] as any),
  eval_summary: ajv.compile(schemas["artifacts/eval_summary.schema.json"] as any),
  control_decision: ajv.compile(schemas["artifacts/control_decision.schema.json"] as any),
  pqx_execution_record: ajv.compile(
    schemas["artifacts/pqx_execution_record.schema.json"] as any
  ),
  failure_artifact: ajv.compile(schemas["artifacts/failure_artifact.schema.json"] as any),
};

export interface ValidationResult {
  valid: boolean;
  errors?: any[];
}

/**
 * Validate any artifact against its schema
 * Returns { valid: boolean, errors?: any[] }
 */
export function validateArtifact(artifact: unknown): ValidationResult {
  if (typeof artifact !== "object" || !artifact) {
    return { valid: false, errors: [{ message: "Artifact must be an object" }] };
  }

  const kind = (artifact as any).artifact_kind;
  const validator = (validators as any)[kind];

  if (!validator) {
    return { valid: false, errors: [{ message: `Unknown artifact kind: ${kind}` }] };
  }

  const valid = validator(artifact);
  return {
    valid,
    errors: valid ? undefined : validator.errors,
  };
}

// Type guards for each artifact type
export function isTranscriptArtifact(artifact: unknown): artifact is TranscriptArtifact {
  return (
    (artifact as any).artifact_kind === "transcript_artifact" && validateArtifact(artifact).valid
  );
}

export function isContextBundle(artifact: unknown): artifact is ContextBundle {
  return (artifact as any).artifact_kind === "context_bundle" && validateArtifact(artifact).valid;
}

export function isAgentExecutionTrace(artifact: unknown): artifact is AgentExecutionTrace {
  return (
    (artifact as any).artifact_kind === "agent_execution_trace" && validateArtifact(artifact).valid
  );
}

export function isEvalCase(artifact: unknown): artifact is EvalCase {
  return (artifact as any).artifact_kind === "eval_case" && validateArtifact(artifact).valid;
}

export function isEvalResult(artifact: unknown): artifact is EvalResult {
  return (artifact as any).artifact_kind === "eval_result" && validateArtifact(artifact).valid;
}

export function isEvalSummary(artifact: unknown): artifact is EvalSummary {
  return (artifact as any).artifact_kind === "eval_summary" && validateArtifact(artifact).valid;
}

export function isControlDecision(artifact: unknown): artifact is ControlDecisionArtifact {
  return (
    (artifact as any).artifact_kind === "control_decision" && validateArtifact(artifact).valid
  );
}

export function isPQXExecutionRecord(artifact: unknown): artifact is PQXExecutionRecord {
  return (
    (artifact as any).artifact_kind === "pqx_execution_record" && validateArtifact(artifact).valid
  );
}

export function isFailureArtifact(artifact: unknown): artifact is FailureArtifact {
  return (artifact as any).artifact_kind === "failure_artifact" && validateArtifact(artifact).valid;
}
