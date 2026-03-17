# Meeting Minutes Examples

Synthetic case library for the Meeting Minutes Engine (SYS-006). All cases are designed for deterministic evaluation and contain no operational data.

## Case index

| Case ID | Directory | Type | Scenario |
| --- | --- | --- | --- |
| CASE-MM-001 | `case-001-standard-working-session/` | standard | Full working session with timestamps, speaker labels, one decision, two action items, one risk |
| CASE-MM-002 | `case-002-high-signal-decisions/` | standard | Decision-dense session with three decisions, multiple action items, and strong traceability signals |
| CASE-MM-003 | `case-003-edge-missing-timestamps/` | edge | Transcript without timestamps; traceability fields cannot be populated — engine must not fabricate them |

## Usage

Load a case by reading `case.yaml` for metadata and expected signals, then supply `transcript.txt` as the transcript input. See `cases/meeting_minutes/case-input-contract.yaml` for the full field reference.

## Adding cases

Follow the naming convention `case-NNN-<short-description>/` and register the new case in this table. Assign the next available `CASE-MM-NNN` ID. Validate `case.yaml` against `cases/meeting_minutes/case-input.schema.json` before submitting.
