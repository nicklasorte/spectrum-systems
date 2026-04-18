export interface MeetingMinutesOutput {
  agenda_items: string[];
  decisions: Array<{ decision: string; rationale: string }>;
  action_items: Array<{ item: string; owner?: string; due_date?: string }>;
  attendees: string[];
}

export interface MinutesExtractionResult {
  success: boolean;
  meeting_minutes_artifact?: any;
  execution_record?: any;
  error?: string;
  error_codes?: string[];
}
