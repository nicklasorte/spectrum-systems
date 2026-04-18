export interface ReviewFinding {
  section: string;
  comment: string;
  severity: "S0" | "S1" | "S2" | "S3" | "S4";
}

export interface ReviewArtifact {
  artifact_kind: "review_artifact";
  artifact_id: string;
  reviewer_id: string;
  decision: "approve" | "reject" | "revise";
  findings: ReviewFinding[];
  timestamp: string;
}

export interface ReviewGatewayResult {
  success: boolean;
  review_artifact?: ReviewArtifact;
  execution_record?: any;
  error?: string;
}
