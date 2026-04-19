# Security: Untrusted Boundary Enforcement

OWASP LLM01 mitigation: strict separation of instructions from untrusted external content.

## Pattern

1. **Detect**: Check transcript for injection-like patterns
2. **Sanitize**: Remove lines that look like instructions
3. **Wrap**: Mark untrusted content in clear delimiters
4. **Instruct**: Tell LLM not to treat marked content as policy
5. **Validate**: Check LLM output for injection patterns

## Usage

```typescript
const boundary = createUntrustedBoundary("transcript", rawTranscript);
const signals = detectInjectionAttempts(rawTranscript);

if (signals.length > 0) {
  throw new Error(`Injection attempt: ${signals}`);
}

const wrappedPrompt = wrapUntrustedInPrompt(boundary, instruction);
const response = await llm.call(wrappedPrompt);
```

## Deployment

Apply boundary enforcement in all LLM calls that consume untrusted content:

- MVP-4: Meeting Minutes Extraction
- MVP-5: Issue Extraction
- MVP-8: Paper Draft Generation
- MVP-11: Revision Integration
