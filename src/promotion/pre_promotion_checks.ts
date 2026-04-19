/**
 * Pre-Promotion Checks for Cluster A
 * Blocks promotion of artifacts with incomplete trace or provenance
 */

import { TraceContext, validateTraceId, validateSpanId } from "../trace/trace_types";
import {
  ProvenanceChain,
  validateProvenanceChain,
  ProvenanceCompleteness,
} from "../provenance/chain_validator";

export interface PrePromotionCheckResult {
  artifact_id: string;
  trace_id: string;
  checks_passed: boolean;
  failed_checks: PrePromotionCheckFailure[];
  warnings: string[];
  promotion_ready: boolean;
  timestamp: string;
}

export interface PrePromotionCheckFailure {
  check_name: string;
  severity: "critical" | "warning";
  description: string;
  remediation: string;
}

export function checkTraceContextValidity(
  traceContext: TraceContext | null
): { valid: boolean; failures: PrePromotionCheckFailure[] } {
  const failures: PrePromotionCheckFailure[] = [];

  if (!traceContext) {
    failures.push({
      check_name: "trace_context_exists",
      severity: "critical",
      description: "No trace context found for artifact",
      remediation: "Ensure artifact is created within active trace context",
    });
    return { valid: false, failures };
  }

  if (!traceContext.traceparent) {
    failures.push({
      check_name: "traceparent_format",
      severity: "critical",
      description: "Traceparent header missing or malformed",
      remediation:
        "Provide valid W3C traceparent in format: version-trace_id-parent_span_id-flags",
    });
    return { valid: false, failures };
  }

  const parts = traceContext.traceparent.split("-");
  if (parts.length !== 4) {
    failures.push({
      check_name: "traceparent_format",
      severity: "critical",
      description: `Invalid traceparent format: expected 4 parts, got ${parts.length}`,
      remediation: "Traceparent must be: version-trace_id-parent_span_id-flags",
    });
  }

  if (parts[0] !== "00") {
    failures.push({
      check_name: "traceparent_version",
      severity: "warning",
      description: `Unexpected trace version: ${parts[0]}`,
      remediation: "Update trace context to use version 00",
    });
  }

  if (!validateTraceId(parts[1])) {
    failures.push({
      check_name: "trace_id_format",
      severity: "critical",
      description: "Trace ID format invalid (must be 32 hex characters)",
      remediation: "Generate valid trace ID using trace_types.generateTraceId()",
    });
  }

  if (!validateSpanId(parts[2])) {
    failures.push({
      check_name: "parent_span_id_format",
      severity: "critical",
      description: "Parent span ID format invalid (must be 16 hex characters)",
      remediation: "Generate valid span ID using trace_types.generateSpanId()",
    });
  }

  return {
    valid: failures.filter((f) => f.severity === "critical").length === 0,
    failures,
  };
}

export function checkProvenanceCompleteness(
  chain: ProvenanceChain | null
): { complete: boolean; completeness: ProvenanceCompleteness | null; failures: PrePromotionCheckFailure[] } {
  const failures: PrePromotionCheckFailure[] = [];

  if (!chain) {
    failures.push({
      check_name: "provenance_chain_exists",
      severity: "critical",
      description: "No provenance chain found for artifact",
      remediation:
        "Capture provenance chain: inputs → code_version → model_version → outputs",
    });
    return { complete: false, completeness: null, failures };
  }

  const completeness = validateProvenanceChain(chain);

  if (!completeness.has_inputs) {
    failures.push({
      check_name: "provenance_inputs",
      severity: "critical",
      description: "Provenance chain missing input artifacts",
      remediation: "Record all input artifacts that fed into the execution",
    });
  }

  if (!completeness.has_code_version) {
    failures.push({
      check_name: "provenance_code_version",
      severity: "critical",
      description: "Provenance chain missing code version",
      remediation: "Record the code version (git commit hash or version tag)",
    });
  }

  if (!completeness.has_model_version) {
    failures.push({
      check_name: "provenance_model_version",
      severity: "critical",
      description: "Provenance chain missing model version",
      remediation: "Record the model version used for execution",
    });
  }

  if (!completeness.has_outputs) {
    failures.push({
      check_name: "provenance_outputs",
      severity: "critical",
      description: "Provenance chain missing output artifacts",
      remediation: "Record all output artifacts produced by the execution",
    });
  }

  return {
    complete: completeness.complete,
    completeness,
    failures,
  };
}

export function runPrePromotionChecks(
  artifactId: string,
  traceId: string,
  traceContext: TraceContext | null,
  provenanceChain: ProvenanceChain | null
): PrePromotionCheckResult {
  const allFailures: PrePromotionCheckFailure[] = [];

  // Check 1: Trace context validity
  const traceCheck = checkTraceContextValidity(traceContext);
  allFailures.push(...traceCheck.failures);

  // Check 2: Provenance completeness
  const provenanceCheck = checkProvenanceCompleteness(provenanceChain);
  allFailures.push(...provenanceCheck.failures);

  const criticalFailures = allFailures.filter((f) => f.severity === "critical");
  const warnings = allFailures.filter((f) => f.severity === "warning").map((f) => f.description);

  return {
    artifact_id: artifactId,
    trace_id: traceId,
    checks_passed: criticalFailures.length === 0,
    failed_checks: criticalFailures,
    warnings,
    promotion_ready: criticalFailures.length === 0 && provenanceCheck.complete,
    timestamp: new Date().toISOString(),
  };
}
