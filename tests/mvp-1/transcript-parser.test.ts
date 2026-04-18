import {
  parseTranscriptTurns,
  extractSpeakers,
  estimateDuration,
  buildMetadata,
  computeContentHash,
  validateTranscript,
} from "../../src/mvp-1/transcript-parser";

describe("Transcript Parser (MVP-1)", () => {
  describe("parseTranscriptTurns", () => {
    it("should parse valid turns", () => {
      const raw = `Alice: Hello.
Bob: Hi there.
Alice: How are you?`;

      const turns = parseTranscriptTurns(raw);

      expect(turns).toHaveLength(3);
      expect(turns[0]).toEqual({
        speaker: "Alice",
        text: "Hello.",
        timestamp: undefined,
        turn_number: 1,
      });
      expect(turns[1].speaker).toBe("Bob");
      expect(turns[2].speaker).toBe("Alice");
    });

    it("should parse turns with timestamps", () => {
      const raw = `Alice: [00:00:00] Good morning.
Bob: [00:01:30] Hi Alice.`;

      const turns = parseTranscriptTurns(raw);

      expect(turns).toHaveLength(2);
      expect(turns[0].timestamp).toBe("00:00:00");
      expect(turns[1].timestamp).toBe("00:01:30");
    });

    it("should skip empty lines", () => {
      const raw = `Alice: First turn.

Bob: Second turn.

Alice: Third turn.`;

      const turns = parseTranscriptTurns(raw);

      expect(turns).toHaveLength(3);
    });

    it("should return empty array for empty input", () => {
      const turns = parseTranscriptTurns("");

      expect(turns).toHaveLength(0);
    });

    it("should ignore malformed lines", () => {
      const raw = `Alice: Valid turn.
This is not a turn.
Bob: Another valid turn.
Neither is this.`;

      const turns = parseTranscriptTurns(raw);

      expect(turns).toHaveLength(2);
    });

    it("should number turns sequentially", () => {
      const raw = `A: Turn 1
B: Turn 2
A: Turn 3`;

      const turns = parseTranscriptTurns(raw);

      expect(turns[0].turn_number).toBe(1);
      expect(turns[1].turn_number).toBe(2);
      expect(turns[2].turn_number).toBe(3);
    });
  });

  describe("extractSpeakers", () => {
    it("should extract unique speakers", () => {
      const turns = [
        { speaker: "Alice", text: "A", turn_number: 1 },
        { speaker: "Bob", text: "B", turn_number: 2 },
        { speaker: "Alice", text: "C", turn_number: 3 },
      ];

      const speakers = extractSpeakers(turns);

      expect(speakers).toHaveLength(2);
      expect(speakers).toContain("Alice");
      expect(speakers).toContain("Bob");
    });
  });

  describe("estimateDuration", () => {
    it("should estimate 2 minutes per turn", () => {
      const turns = [
        { speaker: "A", text: "1", turn_number: 1 },
        { speaker: "B", text: "2", turn_number: 2 },
        { speaker: "C", text: "3", turn_number: 3 },
      ];

      const duration = estimateDuration(turns);

      expect(duration).toBe(6);
    });
  });

  describe("validateTranscript", () => {
    it("should validate good transcript", () => {
      const raw = `Alice: Hello there, this is a good transcript.
Bob: I agree, it has sufficient content.`;
      const turns = parseTranscriptTurns(raw);

      const result = validateTranscript(turns, raw);

      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it("should reject empty turns", () => {
      const result = validateTranscript([], "");

      expect(result.valid).toBe(false);
      expect(result.errors).toContain("Transcript contains no speaker turns");
    });

    it("should reject too-short transcript", () => {
      const turns = [{ speaker: "A", text: "Hi", turn_number: 1 }];
      const raw = "A: Hi";

      const result = validateTranscript(turns, raw);

      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.includes("too short"))).toBe(true);
    });
  });

  describe("computeContentHash", () => {
    it("should compute consistent hash", () => {
      const content = "Alice: Hello world.";
      const hash1 = computeContentHash(content);
      const hash2 = computeContentHash(content);

      expect(hash1).toBe(hash2);
      expect(hash1).toMatch(/^sha256:[a-f0-9]{64}$/);
    });

    it("should differ for different content", () => {
      const hash1 = computeContentHash("Alice: Hello.");
      const hash2 = computeContentHash("Bob: Goodbye.");

      expect(hash1).not.toBe(hash2);
    });
  });
});
