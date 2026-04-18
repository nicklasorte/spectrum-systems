export interface RevisionFinding {
  finding_id: string;
  section: string;
  comment: string;
  severity: string;
  change_applied?: string;
}

export interface RevisedDraftArtifact {
  artifact_kind: "revised_draft_artifact";
  artifact_id: string;
  sections: Record<string, string>;
  revision_diff: RevisionFinding[];
  source_draft_id: string;
  content_hash: string;
}

export interface RevisionIntegrationResult {
  success: boolean;
  revised_draft_artifact?: RevisedDraftArtifact;
  execution_record?: any;
  error?: string;
}
