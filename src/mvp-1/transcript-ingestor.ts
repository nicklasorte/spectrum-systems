import * as crypto from "crypto";
import {
  parseTranscriptTurns,
  parseTranscriptSegments,
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

  const turns = parseTranscriptTurns(input.raw_text);
  const validation = validateTranscript(turns, input.raw_text);

  const makeExecRecord = (
    status: "succeeded" | "failed",
    artifactId?: string,
    failure?: Record<string, unknown>
  ) => ({
    artifact_type: "pqx_execution_record",
    artifact_id: generateId(),
    created_at: new Date().toISOString(),
    trace_id: traceId,
    pqx_step: {
      name: "MVP-1: Transcript Ingestion & Normalization",
      version: "1.0",
    },
    execution_status: status,
    inputs: { artifact_ids: [] },
    outputs: { artifact_ids: artifactId ? [artifactId] : [] },
    timing: {
      started_at: startedAt,
      ended_at: new Date().toISOString(),
    },
    ...(failure && { failure }),
  });

  if (!validation.valid) {
    return {
      success: false,
      error: validation.errors.join("; "),
      error_codes: ["transcript_validation_failed"],
      execution_record: makeExecRecord("failed", undefined, {
        reason_codes: ["transcript_validation_failed"],
        error_message: validation.errors.join("; "),
      }),
    };
  }

  const segments = parseTranscriptSegments(input.raw_text);
  const contentHash = computeContentHash(input.raw_text);
  const artifactId = generateId();
  const meetingId = input.source_file.replace(/\.[^/.]+$/, "");

  const transcriptArtifact = {
    artifact_type: "transcript_artifact" as const,
    schema_version: "1.0.0" as const,
    trace_id: traceId,
    outputs: {
      artifact_id: artifactId,
      metadata: buildMetadata(segments, meetingId),
      source_refs: [input.source_file],
      segments,
      provenance: {
        ingress: input.source_file,
        normalization: "utf8-line-split-v1",
        identity_hash: contentHash,
        content_hash: contentHash,
      },
    },
  };

  return {
    success: true,
    transcript_artifact: transcriptArtifact,
    execution_record: makeExecRecord("succeeded", artifactId),
  };
}
