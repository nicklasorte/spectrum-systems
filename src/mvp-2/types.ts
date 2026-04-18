/**
 * Type definitions for MVP-2: Context Bundle Assembly
 */

export interface ContextBundleAssemblyInput {
  transcript_artifact_id: string;
  task_description?: string;
  instructions?: string;
}

export interface AssemblyManifest {
  input_artifact_ids: string[];
  assembly_version: string;
  assembly_timestamp: string;
  manifest_hash: string;
}

export interface ContextBundlePayload {
  artifact_kind: "context_bundle";
  artifact_id: string;
  created_at: string;
  schema_ref: string;
  trace: {
    trace_id: string;
    created_at: string;
  };
  input_artifacts: string[];
  context: {
    transcript_id: string;
    speakers: string[];
    transcript_content: string;
    task_description: string;
    instructions: string;
  };
  assembly_manifest: AssemblyManifest;
  content_hash: string;
}

export interface ContextBundleAssemblyResult {
  success: boolean;
  context_bundle?: ContextBundlePayload;
  execution_record?: any;
  error?: string;
  error_codes?: string[];
}
