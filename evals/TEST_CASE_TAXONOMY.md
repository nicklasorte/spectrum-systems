# Test Case Taxonomy for Spectrum Systems MVP

## Happy Path (10 cases: test_001–test_010)
- Standard meetings, 2–4 speakers, clear agenda, action items
- Increasing segment counts (8 to 35 segments) across cases
- All with clear structure, traceable issues, complete assignments

## Edge Cases (10 cases: test_011–test_020)
- Very short (2 min): minimal content, single speaker
- Very long (90 min): sustained context
- One speaker: monologue pattern
- Many speakers (20): speaker management scaling
- Overlapping speech / cross-talk
- No agenda: ad-hoc discussion
- Minimal structure: sparse agenda, informal meeting
- Technical jargon: domain-specific language
- Incomplete items: missing assignees, unclear ownership
- Circular dependencies: issue A blocks B, B blocks A

## Failure Modes (10 cases: test_021–test_030)
- Empty object
- Missing required fields (speakers)
- Missing required fields (segments)
- Type mismatches (speaker as string, duration as string)
- Segments lack timestamps
- Huge file (1MB+)
- Segment references non-existent speaker
- Truncated mid-sentence
- Duplicate speakers in array
- Unknown/unstructured format

## Coverage Target
- Happy path: 100%
- Edge cases: 100%
- Failure modes: 100%
- **Total: 30 test cases, locked immutable**
