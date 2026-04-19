export interface PaperSection {
  section_type: string;
  content: string;
  source_issue_ids: string[];
}

export interface PaperDraftArtifact {
  artifact_kind: "paper_draft_artifact";
  artifact_id: string;
  created_at: string;
  schema_ref: string;
  trace: { trace_id: string; created_at: string };
  sections: Record<string, PaperSection>;
  source_issue_set_id: string;
  generation_model: string;
  content_hash: string;
}

export interface PaperGenerationResult {
  success: boolean;
  paper_draft_artifact?: PaperDraftArtifact;
  execution_record?: any;
  error?: string;
  error_codes?: string[];
}
