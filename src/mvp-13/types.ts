export interface DoneCertificationRecord {
  artifact_type: "done_certification_record";
  schema_version: "1.0.0";
  artifact_id: string;
  created_at: string;
  schema_ref: string;
  trace: { trace_id: string; created_at: string };
  status: "PASSED" | "FAILED";
  checks: Record<string, boolean>;
  failures?: string[];
  timestamp: string;
}

export interface ReleaseArtifact {
  artifact_type: "release_artifact";
  schema_version: "1.0.0";
  artifact_id: string;
  created_at: string;
  schema_ref: string;
  trace: { trace_id: string; created_at: string };
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
