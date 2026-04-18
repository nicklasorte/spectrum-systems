import * as crypto from "crypto";
import { createArtifactStore, MemoryStorageBackend } from "../artifact-store";
import {
  parseTranscriptTurns,
  buildMetadata,
  computeContentHash,
  validateTranscript,
} from "./transcript-parser";
import type { TranscriptIngestInput, TranscriptIngestResult } from "./types";

function generateId(): string {
  return crypto.randomUUID();
}

export async function ingestTranscript(
  input: TranscriptIngestInput
): Promise<TranscriptIngestResult> {
  const traceId = generateId();
  const startedAt = new Date().toISOString();
  const traceContext = {
    trace_id: traceId,
    created_at: startedAt,
  };

  const backend = new MemoryStorageBackend();
  const store = createArtifactStore(backend);

  const turns = parseTranscriptTurns(input.raw_text);

  const validation = validateTranscript(turns, input.raw_text);
  if (!validation.valid) {
    return {
      success: false,
      error: validation.errors.join("; "),
      error_codes: ["transcript_validation_failed"],
      execution_record: {
        artifact_kind: "pqx_execution_record",
        artifact_id: generateId(),
        created_at: new Date().toISOString(),
        trace: traceContext,
        pqx_step: {
          name: "MVP-1: Transcript Ingestion & Normalization",
          version: "1.0",
        },
        execution_status: "failed",
        inputs: { artifact_ids: [] },
        outputs: { artifact_ids: [] },
        timing: {
          started_at: startedAt,
          ended_at: new Date().toISOString(),
        },
        failure: {
          reason_codes: ["transcript_validation_failed"],
          error_message: validation.errors.join("; "),
        },
      },
    };
  }

  const metadata = buildMetadata(
    input.raw_text,
    turns,
    input.source_file,
    input.duration_minutes,
    input.language
  );

  const contentHash = computeContentHash(input.raw_text);
  const transcriptArtifact = {
    artifact_kind: "transcript_artifact",
    artifact_id: generateId(),
    created_at: new Date().toISOString(),
    schema_ref: "artifacts/transcript_artifact.schema.json",
    trace: traceContext,
    content: input.raw_text,
    metadata,
    content_hash: contentHash,
  };

  const registrationResult = await store.register(transcriptArtifact);

  if (registrationResult.status !== "accepted") {
    return {
      success: false,
      error: "Failed to register artifact in store",
      error_codes: registrationResult.errors?.map((e) => e.code) || ["registration_failed"],
      execution_record: {
        artifact_kind: "pqx_execution_record",
        artifact_id: generateId(),
        created_at: new Date().toISOString(),
        trace: traceContext,
        pqx_step: {
          name: "MVP-1: Transcript Ingestion & Normalization",
          version: "1.0",
        },
        execution_status: "failed",
        inputs: { artifact_ids: [] },
        outputs: { artifact_ids: [] },
        timing: {
          started_at: startedAt,
          ended_at: new Date().toISOString(),
        },
        failure: {
          reason_codes: ["registration_failed"],
          error_message: `Artifact store rejected registration: ${registrationResult.errors?.[0]?.message || "unknown error"}`,
        },
      },
    };
  }

  const executionRecord = {
    artifact_kind: "pqx_execution_record",
    artifact_id: generateId(),
    created_at: new Date().toISOString(),
    trace: traceContext,
    pqx_step: {
      name: "MVP-1: Transcript Ingestion & Normalization",
      version: "1.0",
    },
    execution_status: "succeeded",
    inputs: { artifact_ids: [] },
    outputs: { artifact_ids: [transcriptArtifact.artifact_id] },
    timing: {
      started_at: startedAt,
      ended_at: new Date().toISOString(),
    },
  };

  return {
    success: true,
    transcript_artifact: transcriptArtifact,
    execution_record: executionRecord,
  };
}
