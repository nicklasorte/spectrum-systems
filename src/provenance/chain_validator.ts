/**
 * Provenance Chain Validator
 * Ensures complete traceability: inputs → code version → model version → outputs
 */

export interface ProvenanceChainLink {
  link_id: string;
  from_artifact_id: string;
  to_artifact_id: string;
  from_kind: string;
  to_kind: string;
  relationship: "inputs_to" | "executed_by" | "produced_by" | "certified_by";
  timestamp: string;
  evidence: string;
}

export interface ProvenanceChain {
  trace_id: string;
  artifact_id: string;
  chain_links: ProvenanceChainLink[];
  input_artifacts: string[];
  execution_context: {
    code_version: string;
    model_version: string;
    runtime_version: string;
  };
  output_artifacts: string[];
  chain_complete: boolean;
  chain_verification_timestamp: string;
}

export interface ProvenanceCompleteness {
  trace_id: string;
  artifact_id: string;
  has_inputs: boolean;
  has_code_version: boolean;
  has_model_version: boolean;
  has_outputs: boolean;
  complete: boolean;
  missing_elements: string[];
}

export function validateProvenanceChain(
  chain: ProvenanceChain
): ProvenanceCompleteness {
  const missing: string[] = [];

  if (!chain.input_artifacts || chain.input_artifacts.length === 0) {
    missing.push("input_artifacts");
  }

  if (!chain.execution_context?.code_version) {
    missing.push("code_version");
  }

  if (!chain.execution_context?.model_version) {
    missing.push("model_version");
  }

  if (!chain.output_artifacts || chain.output_artifacts.length === 0) {
    missing.push("output_artifacts");
  }

  const linksValid =
    chain.chain_links && chain.chain_links.length >= 3; // min: input, execution, output
  if (!linksValid) {
    missing.push("chain_links");
  }

  return {
    trace_id: chain.trace_id,
    artifact_id: chain.artifact_id,
    has_inputs: chain.input_artifacts && chain.input_artifacts.length > 0,
    has_code_version: !!chain.execution_context?.code_version,
    has_model_version: !!chain.execution_context?.model_version,
    has_outputs: chain.output_artifacts && chain.output_artifacts.length > 0,
    complete: missing.length === 0,
    missing_elements: missing,
  };
}

export function reconstructCausalPath(
  chain: ProvenanceChain
): { path: string[]; complete: boolean } {
  const path: string[] = [];

  // Start with inputs
  path.push(...(chain.input_artifacts || []));

  // Add execution context
  if (chain.execution_context?.code_version) {
    path.push(`code:${chain.execution_context.code_version}`);
  }
  if (chain.execution_context?.model_version) {
    path.push(`model:${chain.execution_context.model_version}`);
  }

  // Add outputs
  path.push(...(chain.output_artifacts || []));

  const complete = path.length >= 3;
  return { path, complete };
}

export function verifyReplayFidelity(
  originalChain: ProvenanceChain,
  replayChain: ProvenanceChain
): {
  fidelity_match: boolean;
  divergences: string[];
} {
  const divergences: string[] = [];

  // Check code version match
  if (
    originalChain.execution_context?.code_version !==
    replayChain.execution_context?.code_version
  ) {
    divergences.push("code_version_mismatch");
  }

  // Check model version match
  if (
    originalChain.execution_context?.model_version !==
    replayChain.execution_context?.model_version
  ) {
    divergences.push("model_version_mismatch");
  }

  // Check input count match
  if (
    (originalChain.input_artifacts?.length || 0) !==
    (replayChain.input_artifacts?.length || 0)
  ) {
    divergences.push("input_count_mismatch");
  }

  // Check output count match
  if (
    (originalChain.output_artifacts?.length || 0) !==
    (replayChain.output_artifacts?.length || 0)
  ) {
    divergences.push("output_count_mismatch");
  }

  return {
    fidelity_match: divergences.length === 0,
    divergences,
  };
}

export function createProvenanceChain(
  traceId: string,
  artifactId: string,
  inputArtifacts: string[],
  executionContext: {
    code_version: string;
    model_version: string;
    runtime_version: string;
  },
  outputArtifacts: string[],
  chainLinks: ProvenanceChainLink[]
): ProvenanceChain {
  return {
    trace_id: traceId,
    artifact_id: artifactId,
    chain_links: chainLinks,
    input_artifacts: inputArtifacts,
    execution_context: executionContext,
    output_artifacts: outputArtifacts,
    chain_complete:
      inputArtifacts.length > 0 &&
      !!executionContext.code_version &&
      !!executionContext.model_version &&
      outputArtifacts.length > 0 &&
      chainLinks.length >= 3,
    chain_verification_timestamp: new Date().toISOString(),
  };
}
