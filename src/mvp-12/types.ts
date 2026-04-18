export interface FormattedPaperArtifact {
  artifact_kind: "formatted_paper_artifact";
  artifact_id: string;
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
}
