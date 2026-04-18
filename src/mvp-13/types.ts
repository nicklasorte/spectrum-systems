export interface DoneCertificationRecord {
  artifact_kind: "done_certification_record";
  artifact_id: string;
  status: "PASSED" | "FAILED";
  checks: Record<string, boolean>;
  failures?: string[];
  timestamp: string;
}

export interface ReleaseArtifact {
  artifact_kind: "release_artifact";
  artifact_id: string;
  formatted_paper_id: string;
  certification_id: string;
  status: "RELEASED";
  timestamp: string;
}

export interface GOV10CertificationResult {
  success: boolean;
  done_certification_record?: DoneCertificationRecord;
  release_artifact?: ReleaseArtifact;
  execution_record?: any;
  error?: string;
}
