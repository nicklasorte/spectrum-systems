import { Anthropic } from "@anthropic-ai/sdk";
import {
  createUntrustedBoundary,
  wrapUntrustedInPrompt,
  detectInjectionAttempts,
} from "@/src/security/untrusted-boundary";

/**
 * MVP-4 with injection boundary enforcement
 * Transcript is treated as untrusted external content
 */

export async function extractMeetingMinutesHardened(
  contextBundle: any
): Promise<any> {
  const client = new Anthropic();

  // Step 1: Detect injection attempts in raw transcript
  const injectionSignals = detectInjectionAttempts(
    contextBundle.context.transcript_content
  );

  if (injectionSignals.length > 0) {
    return {
      success: false,
      error: `Injection attempt detected in transcript: ${injectionSignals.join(", ")}`,
      error_codes: ["injection_detected"],
    };
  }

  // Step 2: Wrap transcript in untrusted boundary
  const untrustedTranscript = createUntrustedBoundary(
    "meeting_transcript",
    contextBundle.context.transcript_content
  );

  // Step 3: Build prompt with clear separation of instruction vs data
  const instruction = `Extract meeting minutes from the provided transcript.
Focus on: agenda items, decisions made, action items, and attendees.
Return ONLY valid JSON with no preamble or explanation.`;

  const wrappedPrompt = wrapUntrustedInPrompt(untrustedTranscript, instruction);

  // Step 4: Call LLM with hardened prompt
  const response = await client.messages.create({
    model: "claude-3-5-haiku-20241022",
    max_tokens: 2000,
    messages: [{ role: "user", content: wrappedPrompt }],
  });

  const textContent = response.content.find((c) => c.type === "text");
  if (!textContent || textContent.type !== "text") {
    return { success: false, error: "No response from model" };
  }

  // Step 5: Validate output doesn't contain injected instructions
  const outputInjectionSignals = detectInjectionAttempts(textContent.text);
  if (outputInjectionSignals.length > 0) {
    return {
      success: false,
      error: `Injection patterns detected in model output: ${outputInjectionSignals.join(", ")}`,
      error_codes: ["output_injection_detected"],
    };
  }

  // Parse and return
  const jsonMatch = textContent.text.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    return { success: false, error: "Could not parse JSON from response" };
  }

  return { success: true, minutes: JSON.parse(jsonMatch[0]) };
}
