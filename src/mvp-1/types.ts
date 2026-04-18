export interface TranscriptTurn {
  speaker: string;
  text: string;
  timestamp?: string;
  turn_number: number;
}

export interface TranscriptMetadata {
  speaker_labels: string[];
  turn_count: number;
  duration_minutes: number;
  language: string;
  source_file: string;
  file_size_bytes: number;
  processed_at: string;
}

export interface TranscriptIngestInput {
  raw_text: string;
  source_file: string;
  duration_minutes?: number;
  language?: string;
}

export interface TranscriptIngestResult {
  success: boolean;
  transcript_artifact?: any;
  execution_record: any;
  error?: string;
  error_codes?: string[];
}
