export interface Issue {
  issue_id: string;
  type: "finding" | "action_item" | "risk";
  description: string;
  priority: "high" | "medium" | "low";
  assignee?: string;
  status: "open" | "closed";
  source_turn_ref: string;
}

export interface IssueRegistryArtifact {
  artifact_type: "issue_registry_artifact";
  schema_version: "1.0.0";
  artifact_id: string;
  created_at: string;
  schema_ref: string;
  trace: { trace_id: string; created_at: string };
  source_transcript_id: string;
  source_context_bundle_id: string;
  source_minutes_id: string;
  issues: Issue[];
  extraction_model: string;
  content_hash: string;
}

export interface IssueExtractionResult {
  success: boolean;
  issue_registry_artifact?: any;
  execution_record?: any;
  error?: string;
  error_codes?: string[];
}
