# MVP-8: Paper Draft Generation

HARDEST STEP. Core AI generation.

## Strategy

Section-by-section:
1. Build section context
2. Call Sonnet
3. Validate immediately
4. Retry up to 3 times on failure
5. Fail-closed on all failures

## Sections

- abstract
- introduction
- findings (spectrum findings)
- recommendations (policy recommendations)
- conclusion

## Key

Output must conform to schema. Fail-closed on mismatch.

## Model

Sonnet. All calls seeded for replay.
