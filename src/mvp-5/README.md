# MVP-5: Issue Extraction

Extracts spectrum-relevant issues and action items.

## CRITICAL

Every issue must have source_turn_ref — direct quote from transcript.

## Output

issue_registry_artifact with:
- issue_id
- type: finding | action_item | risk
- description
- priority: high | medium | low
- assignee (optional)
- status: open | closed
- source_turn_ref (CRITICAL - traceable)

## Model

Haiku (structured extraction with source traceability).
