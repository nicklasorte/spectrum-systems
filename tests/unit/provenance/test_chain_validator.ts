/**
 * Unit tests for Provenance Chain Validator
 */

import {
  createProvenanceChain,
  validateProvenanceChain,
  reconstructCausalPath,
  verifyReplayFidelity,
} from "../../../src/provenance/chain_validator";
import { v4 as uuidv4 } from "uuid";

describe("Provenance Chain Validator", () => {
  const mockChainLinks = [
    {
      link_id: uuidv4(),
      from_artifact_id: "input-1",
      to_artifact_id: "exec-1",
      from_kind: "input",
      to_kind: "execution",
      relationship: "inputs_to" as const,
      timestamp: new Date().toISOString(),
      evidence: "artifact flow record",
    },
    {
      link_id: uuidv4(),
      from_artifact_id: "exec-1",
      to_artifact_id: "output-1",
      from_kind: "execution",
      to_kind: "output",
      relationship: "produced_by" as const,
      timestamp: new Date().toISOString(),
      evidence: "execution log",
    },
  ];

  test("createProvenanceChain creates complete chain", () => {
    const traceId = uuidv4();
    const artifactId = uuidv4();

    const chain = createProvenanceChain(
      traceId,
      artifactId,
      ["input-1", "input-2"],
      {
        code_version: "abc123",
        model_version: "model-v1.2.3",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      mockChainLinks
    );

    expect(chain.trace_id).toBe(traceId);
    expect(chain.artifact_id).toBe(artifactId);
    expect(chain.chain_complete).toBe(true);
    expect(chain.input_artifacts).toHaveLength(2);
    expect(chain.output_artifacts).toHaveLength(1);
  });

  test("validateProvenanceChain detects missing inputs", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      [], // empty inputs
      {
        code_version: "abc123",
        model_version: "model-v1.2.3",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      mockChainLinks
    );

    const completeness = validateProvenanceChain(chain);
    expect(completeness.complete).toBe(false);
    expect(completeness.has_inputs).toBe(false);
    expect(completeness.missing_elements).toContain("input_artifacts");
  });

  test("validateProvenanceChain detects missing code version", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "", // empty
        model_version: "model-v1.2.3",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      mockChainLinks
    );

    const completeness = validateProvenanceChain(chain);
    expect(completeness.complete).toBe(false);
    expect(completeness.has_code_version).toBe(false);
  });

  test("validateProvenanceChain detects missing model version", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "abc123",
        model_version: "", // empty
        runtime_version: "1.0.0",
      },
      ["output-1"],
      mockChainLinks
    );

    const completeness = validateProvenanceChain(chain);
    expect(completeness.complete).toBe(false);
    expect(completeness.has_model_version).toBe(false);
  });

  test("validateProvenanceChain detects missing outputs", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "abc123",
        model_version: "model-v1.2.3",
        runtime_version: "1.0.0",
      },
      [], // empty outputs
      mockChainLinks
    );

    const completeness = validateProvenanceChain(chain);
    expect(completeness.complete).toBe(false);
    expect(completeness.has_outputs).toBe(false);
  });

  test("reconstructCausalPath builds complete path", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1", "input-2"],
      {
        code_version: "abc123",
        model_version: "model-v1.2.3",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      mockChainLinks
    );

    const { path, complete } = reconstructCausalPath(chain);

    expect(complete).toBe(true);
    expect(path).toContain("input-1");
    expect(path).toContain("input-2");
    expect(path).toContain("code:abc123");
    expect(path).toContain("model:model-v1.2.3");
    expect(path).toContain("output-1");
  });

  test("verifyReplayFidelity detects code version mismatch", () => {
    const originalChain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "abc123",
        model_version: "model-v1.2.3",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      mockChainLinks
    );

    const replayChain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "def456", // different
        model_version: "model-v1.2.3",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      mockChainLinks
    );

    const { fidelity_match, divergences } = verifyReplayFidelity(originalChain, replayChain);
    expect(fidelity_match).toBe(false);
    expect(divergences).toContain("code_version_mismatch");
  });

  test("verifyReplayFidelity detects model version mismatch", () => {
    const originalChain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "abc123",
        model_version: "model-v1.2.3",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      mockChainLinks
    );

    const replayChain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "abc123",
        model_version: "model-v1.3.0", // different
        runtime_version: "1.0.0",
      },
      ["output-1"],
      mockChainLinks
    );

    const { fidelity_match, divergences } = verifyReplayFidelity(originalChain, replayChain);
    expect(fidelity_match).toBe(false);
    expect(divergences).toContain("model_version_mismatch");
  });

  test("verifyReplayFidelity passes with identical chains", () => {
    const chain = createProvenanceChain(
      uuidv4(),
      uuidv4(),
      ["input-1"],
      {
        code_version: "abc123",
        model_version: "model-v1.2.3",
        runtime_version: "1.0.0",
      },
      ["output-1"],
      mockChainLinks
    );

    const { fidelity_match, divergences } = verifyReplayFidelity(chain, chain);
    expect(fidelity_match).toBe(true);
    expect(divergences).toHaveLength(0);
  });
});
