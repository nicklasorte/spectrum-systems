export interface FormattedPaperArtifact {
  artifact_type: "formatted_paper_artifact";
  schema_version: "1.0.0";
  artifact_id: string;
  created_at: string;
  schema_ref: string;
  trace: { trace_id: string; created_at: string };
  title: string;
  sections: Record<string, string>;
  publication_metadata: {
    doi_placeholder: string;
    version: string;
    authors: string[];
    date: string;
  };
  content_hash: string;
}

export interface PublicationFormattingResult {
  success: boolean;
  formatted_paper_artifact?: FormattedPaperArtifact;
  execution_record?: any;
  error?: string;
  error_codes?: string[];
}
