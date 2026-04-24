export interface TranscriptTurn {
  speaker: string;
  text: string;
  timestamp?: string;
  turn_number: number;
}

export interface TranscriptSegment {
  segment_id: string;
  speaker: string;
  agency: string;
  text: string;
  timestamp?: string;
}

export interface TranscriptArtifactMetadata {
  segment_count: number;
  has_timestamps: boolean;
  meeting_id: string;
}

export interface TranscriptArtifactProvenance {
  ingress: string;
  normalization: string;
  identity_hash: string;
  content_hash: string;
}

export interface TranscriptArtifactOutputs {
  artifact_id: string;
  metadata: TranscriptArtifactMetadata;
  source_refs: string[];
  segments: TranscriptSegment[];
  provenance: TranscriptArtifactProvenance;
}

export interface TranscriptArtifact {
  artifact_type: "transcript_artifact";
  schema_version: "1.0.0";
  trace_id: string;
  outputs: TranscriptArtifactOutputs;
}

export interface TranscriptIngestInput {
  raw_text: string;
  source_file: string;
  duration_minutes?: number;
  language?: string;
}

export interface TranscriptIngestResult {
  success: boolean;
  transcript_artifact?: TranscriptArtifact;
  execution_record: any;
  error?: string;
  error_codes?: string[];
}
