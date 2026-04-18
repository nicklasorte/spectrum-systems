import * as crypto from "crypto";
import type { TranscriptTurn, TranscriptMetadata } from "./types";

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
  rawText: string,
  turns: TranscriptTurn[],
  sourceFile: string,
  durationMinutes?: number,
  language?: string
): TranscriptMetadata {
  return {
    speaker_labels: extractSpeakers(turns),
    turn_count: turns.length,
    duration_minutes: durationMinutes || estimateDuration(turns),
    language: language || "en",
    source_file: sourceFile,
    file_size_bytes: Buffer.byteLength(rawText, "utf-8"),
    processed_at: new Date().toISOString(),
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
