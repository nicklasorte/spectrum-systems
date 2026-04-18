# MVP-4: Meeting Minutes Extraction

First AI-driven step. Uses Haiku to extract structured minutes.

## Output

meeting_minutes_artifact with:
- agenda_items: list
- decisions: with rationale
- action_items: with owner/due_date
- attendees: list

## Key

Output must conform to schema — fail-closed on mismatch.

## Model

Claude Haiku (structured extraction).
