import * as crypto from "crypto";
import type {
  TranscriptTurn,
  TranscriptSegment,
  TranscriptArtifactMetadata,
} from "./types";

export function parseTranscriptTurns(rawText: string): TranscriptTurn[] {
  if (!rawText || rawText.trim().length === 0) {
    return [];
  }

  const lines = rawText.split("\n");
  const turns: TranscriptTurn[] = [];
  let turnNumber = 0;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    // Match "Speaker: text" or "Speaker: [HH:MM:SS] text"
    const match = trimmed.match(/^([^:]+?):\s*(?:\[(\d{2}:\d{2}:\d{2})\]\s+)?(.+)$/);

    if (match) {
      turnNumber++;
      turns.push({
        speaker: match[1].trim(),
        timestamp: match[2] || undefined,
        text: match[3].trim(),
        turn_number: turnNumber,
      });
    }
  }

  return turns;
}

export function parseTranscriptSegments(rawText: string): TranscriptSegment[] {
  const turns = parseTranscriptTurns(rawText);
  return turns.map((turn) => {
    const segment: TranscriptSegment = {
      segment_id: crypto.randomUUID(),
      speaker: turn.speaker,
      agency: "UNKNOWN",
      text: turn.text,
    };
    if (turn.timestamp !== undefined) {
      segment.timestamp = turn.timestamp;
    }
    return segment;
  });
}

export function extractSpeakers(turns: TranscriptTurn[]): string[] {
  const speakers = new Set<string>();
  for (const turn of turns) {
    speakers.add(turn.speaker);
  }
  return Array.from(speakers);
}

export function estimateDuration(turns: TranscriptTurn[]): number {
  return Math.max(turns.length * 2, 1);
}

export function buildMetadata(
  segments: TranscriptSegment[],
  meetingId: string
): TranscriptArtifactMetadata {
  return {
    segment_count: segments.length,
    has_timestamps: segments.some((s) => s.timestamp !== undefined),
    meeting_id: meetingId,
  };
}

export function computeContentHash(content: string): string {
  const hash = crypto.createHash("sha256").update(content).digest("hex");
  return `sha256:${hash}`;
}

export function validateTranscript(
  turns: TranscriptTurn[],
  rawText: string
): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (turns.length === 0) {
    errors.push("Transcript contains no speaker turns");
  }

  if (rawText.trim().length < 50) {
    errors.push("Transcript too short (minimum 50 characters)");
  }

  for (const turn of turns) {
    if (!turn.speaker || turn.speaker.trim().length === 0) {
      errors.push("Found turn with empty speaker label");
      break;
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}
