export interface RevisionFinding {
  finding_id: string;
  section: string;
  comment: string;
  severity: string;
  change_applied?: string;
}

export interface RevisedDraftArtifact {
  artifact_type: "revised_draft_artifact";
  schema_version: "1.0.0";
  artifact_id: string;
  created_at: string;
  schema_ref: string;
  trace: { trace_id: string; created_at: string };
  sections: Record<string, any>;
  revision_diff: RevisionFinding[];
  source_draft_id: string;
  content_hash: string;
}

export interface RevisionIntegrationResult {
  success: boolean;
  revised_draft_artifact?: RevisedDraftArtifact;
  execution_record?: any;
  error?: string;
  error_codes?: string[];
}
