# MVP-11: Revision Integration

Applies reviewer findings to draft.

## Process

1. For each S2+ finding
2. Extract section target
3. Call Sonnet with: original text + finding comment
4. Sonnet generates revised text
5. Track change in revision_diff

## Output

revised_draft_artifact with:
- All revised sections
- revision_diff (finding_id → change)

## Model

Sonnet. All calls seeded.
