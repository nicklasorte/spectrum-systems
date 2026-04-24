/**
 * MVP-2: Context Bundle Assembly
 *
 * Input: transcript_artifact (full object from MVP-1)
 * Output: context_bundle (schema v2.3.0, deterministic assembly_manifest_hash)
 *
 * Key property: Same transcript_artifact always produces same assembly_manifest_hash
 * (enables replay and verification). No randomness in hash computation.
 */

import * as crypto from "crypto";
import type { ContextBundleAssemblyResult, ContextBundlePayload, ContextItem } from "./types";

const DEFAULT_TASK_TYPE = "spectrum_analysis";

export async function assembleContextBundle(
  transcriptArtifact: Record<string, any> | null | undefined,
  options?: { task_description?: string; instructions?: string }
): Promise<ContextBundleAssemblyResult> {
  const startedAt = new Date().toISOString();
  const traceId = crypto.randomUUID();

  // Step 1: Validate transcript artifact — must have outputs.artifact_id
  const artifactId = transcriptArtifact?.outputs?.artifact_id;
  if (!transcriptArtifact || typeof transcriptArtifact !== "object" || !artifactId) {
    const errorMessage =
      "Transcript artifact is required and must have an artifact_id";
    return {
      success: false,
      error: errorMessage,
      error_codes: ["missing_artifact"],
      execution_record: buildExecutionRecord({
        traceId,
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

  const transcriptArtifactId = artifactId as string;

  // Step 2: Build deterministic assembly manifest hash.
  // Inputs are stable — no timestamps or random values — so same transcript always
  // produces the same hash.
  const contentHash =
    transcriptArtifact.outputs?.provenance?.content_hash || "";
  const manifestHashInput = JSON.stringify({
    input_artifact_ids: [transcriptArtifactId],
    content_hash: contentHash,
  });
  const manifestHash = computeHash(manifestHashInput);

  // Step 3: Extract transcript segments for the primary_input context item
  const segments: any[] = transcriptArtifact.outputs?.segments || [];

  // Step 4: Generate IDs with required prefix patterns
  const contextBundleId = "ctx-" + crypto.randomBytes(8).toString("hex");
  const contextId = "ctx-" + crypto.randomBytes(8).toString("hex");
  const itemId = "ctxi-" + crypto.randomBytes(8).toString("hex");

  // Step 5: Build context_items with one primary_input entry
  const contextItem: ContextItem = {
    item_index: 0,
    item_id: itemId,
    item_type: "primary_input",
    trust_level: "high",
    source_classification: "internal",
    provenance_ref: transcriptArtifactId,
    provenance_refs: [transcriptArtifactId],
    content: segments,
  };

  // Step 6: Build the context bundle (schema v2.3.0)
  const contextBundle: ContextBundlePayload = {
    artifact_type: "context_bundle",
    schema_version: "2.3.0",
    context_bundle_id: contextBundleId,
    context_id: contextId,
    task_type: options?.task_description || DEFAULT_TASK_TYPE,
    created_at: startedAt,
    trace: {
      trace_id: traceId,
      run_id: traceId,
    },
    context_items: [contextItem],
    source_segmentation: {
      classification_order: ["internal", "external", "inferred", "user_provided"],
      classification_counts: { internal: 1, external: 0, inferred: 0, user_provided: 0 },
      item_refs_by_class: {
        internal: [itemId],
        external: [],
        inferred: [],
        user_provided: [],
      },
      grounded_item_refs: [itemId],
      inferred_item_refs: [],
    },
    primary_input: {},
    policy_constraints: {},
    retrieved_context: [],
    prior_artifacts: [],
    glossary_terms: [],
    glossary_definitions: [],
    glossary_canonicalization: {
      injection_enabled: false,
      match_mode: "exact",
      selection_mode: "explicit_then_exact_text",
      fail_on_missing_required: false,
      selected_glossary_entry_ids: [],
      unresolved_terms: [],
    },
    unresolved_questions: [],
    metadata: {
      assembly_manifest_hash: manifestHash,
      input_artifact_ids: [transcriptArtifactId],
    },
    token_estimates: {
      primary_input: 0,
      policy_constraints: 0,
      prior_artifacts: 0,
      retrieved_context: 0,
      glossary_terms: 0,
      glossary_definitions: 0,
      unresolved_questions: 0,
      total: 0,
    },
    truncation_log: [],
    priority_order: [],
  };

  // Step 7: Emit execution record
  const endedAt = new Date().toISOString();
  const executionRecord = buildExecutionRecord({
    traceId,
    startedAt,
    endedAt,
    status: "succeeded",
    inputIds: [transcriptArtifactId],
    outputIds: [contextBundleId],
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
  traceId: string;
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
    trace: { trace_id: params.traceId, created_at: params.startedAt },
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
