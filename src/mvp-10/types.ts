export interface ReviewFinding {
  finding_id?: string;
  section: string;
  comment: string;
  severity: "S0" | "S1" | "S2" | "S3" | "S4";
}

export interface ReviewArtifact {
  artifact_type: "review_artifact";
  schema_version: "1.0.0";
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
  error_codes?: string[];
}
