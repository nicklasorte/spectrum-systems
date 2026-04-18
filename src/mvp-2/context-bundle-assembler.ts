/**
 * MVP-2: Context Bundle Assembly
 *
 * Input: transcript_artifact (full object from MVP-1)
 * Output: context_bundle (deterministic assembly with reproducible manifest hash)
 *
 * Key property: Same transcript_artifact always produces same context_bundle
 * with same content_hash (enables replay and verification).
 *
 * The context_bundle is the standard input for all downstream LLM steps (MVP-4, MVP-5, etc).
 * Assembly is fully deterministic — no randomness in hash computation.
 */

import * as crypto from "crypto";
import { createArtifactStore, MemoryStorageBackend } from "../artifact-store";
import type { ContextBundleAssemblyResult, ContextBundlePayload } from "./types";

const DEFAULT_TASK_DESCRIPTION =
  "Extract and analyze spectrum findings from meeting transcript";
const DEFAULT_INSTRUCTIONS = "Structured extraction with schema validation";

export async function assembleContextBundle(
  transcriptArtifact: Record<string, any> | null | undefined,
  options?: { task_description?: string; instructions?: string }
): Promise<ContextBundleAssemblyResult> {
  const startedAt = new Date().toISOString();
  const traceId = crypto.randomUUID();
  const traceContext = {
    trace_id: traceId,
    created_at: startedAt,
  };

  // Step 1: Validate transcript artifact
  if (
    !transcriptArtifact ||
    typeof transcriptArtifact !== "object" ||
    !transcriptArtifact.artifact_id
  ) {
    const errorMessage =
      "Transcript artifact is required and must have an artifact_id";
    return {
      success: false,
      error: errorMessage,
      error_codes: ["missing_artifact"],
      execution_record: buildExecutionRecord({
        traceContext,
        startedAt,
        status: "failed",
        inputIds: [],
        outputIds: [],
        failure: {
          reason_codes: ["missing_artifact"],
          error_message: errorMessage,
        },
      }),
    };
  }

  const transcriptArtifactId = transcriptArtifact.artifact_id as string;

  // Step 2: Build deterministic assembly manifest
  // Hash inputs are stable — no timestamps or random values included.
  // Same transcript_artifact always produces the same hash.
  const stableManifestInput = JSON.stringify({
    input_artifact_ids: [transcriptArtifactId],
    assembly_version: "1.0",
    transcript_content_hash: transcriptArtifact.content_hash || "",
  });
  const manifestHash = computeHash(stableManifestInput);

  // Step 3: Extract transcript data
  const speakers: string[] = transcriptArtifact.metadata?.speaker_labels || [];
  const transcriptContent: string = transcriptArtifact.content || "";
  const taskDescription =
    options?.task_description || DEFAULT_TASK_DESCRIPTION;
  const instructions = options?.instructions || DEFAULT_INSTRUCTIONS;

  // content_hash covers all stable context — same inputs always produce same hash
  const stableContentInput = JSON.stringify({
    transcript_id: transcriptArtifactId,
    transcript_content_hash: transcriptArtifact.content_hash || "",
    task_description: taskDescription,
    instructions,
    assembly_version: "1.0",
  });
  const contentHash = computeHash(stableContentInput);

  // Step 4: Build context bundle
  const contextBundle: ContextBundlePayload = {
    artifact_kind: "context_bundle",
    artifact_id: crypto.randomUUID(),
    created_at: startedAt,
    schema_ref: "artifacts/context_bundle.schema.json",
    trace: traceContext,
    input_artifacts: [transcriptArtifactId],
    context: {
      transcript_id: transcriptArtifactId,
      speakers,
      transcript_content: transcriptContent,
      task_description: taskDescription,
      instructions,
    },
    assembly_manifest: {
      input_artifact_ids: [transcriptArtifactId],
      assembly_version: "1.0",
      assembly_timestamp: startedAt,
      manifest_hash: manifestHash,
    },
    content_hash: contentHash,
  };

  // Step 5: Register context bundle in artifact store
  const backend = new MemoryStorageBackend();
  const store = createArtifactStore(backend);
  const registrationResult = await store.register(contextBundle);

  if (registrationResult.status !== "accepted") {
    return {
      success: false,
      error: "Failed to register context bundle in artifact store",
      error_codes: ["registration_failed"],
      execution_record: buildExecutionRecord({
        traceContext,
        startedAt,
        status: "failed",
        inputIds: [transcriptArtifactId],
        outputIds: [],
        failure: {
          reason_codes: ["registration_failed"],
          error_message: "Artifact store rejected registration",
        },
      }),
    };
  }

  // Step 6: Emit execution record
  const endedAt = new Date().toISOString();
  const executionRecord = buildExecutionRecord({
    traceContext,
    startedAt,
    endedAt,
    status: "succeeded",
    inputIds: [transcriptArtifactId],
    outputIds: [contextBundle.artifact_id],
  });

  return {
    success: true,
    context_bundle: contextBundle,
    execution_record: executionRecord,
  };
}

function computeHash(content: string): string {
  const hash = crypto.createHash("sha256").update(content).digest("hex");
  return `sha256:${hash}`;
}

function buildExecutionRecord(params: {
  traceContext: { trace_id: string; created_at: string };
  startedAt: string;
  endedAt?: string;
  status: string;
  inputIds: string[];
  outputIds: string[];
  failure?: { reason_codes: string[]; error_message: string };
}): any {
  const record: any = {
    artifact_kind: "pqx_execution_record",
    artifact_id: crypto.randomUUID(),
    created_at: params.endedAt || params.startedAt,
    trace: params.traceContext,
    pqx_step: {
      name: "MVP-2: Context Bundle Assembly",
      version: "1.0",
    },
    execution_status: params.status,
    inputs: { artifact_ids: params.inputIds },
    outputs: { artifact_ids: params.outputIds },
    timing: {
      started_at: params.startedAt,
      ended_at: params.endedAt || params.startedAt,
    },
  };
  if (params.failure) {
    record.failure = params.failure;
  }
  return record;
}
