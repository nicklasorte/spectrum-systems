# Meeting Agenda Contract (canonical agenda-generation interface)

This contract governs how the czar repo org generates the next meeting agenda from prior minutes, comment resolution matrices, submitted comments, and optional context notes. It defines machine-readable and human-readable outputs that downstream engines must honor.

## Purpose
- Produce the **next upcoming meeting agenda** using prior meeting minutes, the comment resolution matrix, optional submitted comments, prior agendas, and context/policy notes.
- Emit deterministic, traceable artifacts in both machine-readable (JSON) and human-readable (Markdown/DOCX) forms.
- Preserve links back to every source artifact so decisions and carry-forward items remain auditable.

## Required inputs (concepts + contract roles)
- `prior_minutes` — structured minutes aligned to `contracts/meeting_minutes_contract.yaml`.
- `resolution_matrix` — canonical comment resolution matrix (`contracts/schemas/comment_resolution_matrix.schema.json`).
- `submitted_comments` (optional) — raw/submitted comments to backfill context where matrix rows are pending.
- `prior_agenda` (optional) — previous agenda to carry timeboxed items forward.
- `policy_context` (optional) — context/policy notes influencing ordering or emphasis.

## Required outputs (fields in the schema)
- `meeting_title`
- `meeting_objective`
- `source_artifacts` (traceable list of inputs with roles)
- `agenda_items` (ordered)
- `carry_forward_items`
- `decisions_needed`
- `risks_blockers`
- `pre_reads`
- `suggested_attendees`

### Source artifact entries
Each `source_artifacts` entry includes `artifact_id`, `artifact_type`, `artifact_version`, `role`, `source_repo`, and `source_repo_version`; optional `location` and `notes` can capture URIs or handling instructions for traceability.

## Agenda item schema (canonical fields)
Each agenda item **must** carry these fields (see `contracts/schemas/meeting_agenda_contract.schema.json`):
- `agenda_id` — stable identifier.
- `section` — grouping (Decision, Review, Risk, Info, etc.).
- `title` — concise agenda label.
- `description` — succinct context/intent.
- `source_refs` — array of `source_reference` objects tying back to minutes topics/actions, matrix comment IDs, submitted comment IDs, or supporting docs.
- `status_basis` — why the item is on the agenda (`unresolved_comment`, `open_action_item`, `pending_decision`, `new_submission`, `risk_escalation`, `carry_forward`, `context_alignment`).
- `recommended_outcome` — target outcome/decision text.
- `proposed_owner` — accountable owner for driving the item.
- `proposed_speakers` — array of `{name, role, organization?}`.
- `estimated_minutes` — numeric estimate.
- `priority` — `high` | `medium` | `low`.
- `pre_read_required` — boolean.
- `pre_read_refs` — supporting `source_reference` entries for pre-reads.

## Source reference schema (traceability)
Use `source_reference` objects to point back to:
- `minutes_topic` — e.g., topic identifiers with timestamp or page/line.
- `minutes_action_item` — action item IDs with timestamps.
- `resolution_matrix_comment` — comment IDs from the matrix.
- `submitted_comment` — raw/submitted comment IDs when matrix context is thin.
- `supporting_document` — any supporting doc with URI/path and location metadata.
Fields: `ref_type` (enum above), `ref_id`, optional `description`, `location`, `link`, `provenance_id`.

## Generation rules (engines must enforce)
- **Carry forward** unresolved/open/partial/pending items from minutes and prior agendas.
- **Elevate** decision-required issues into a dedicated decision section (tagged via `status_basis=pending_decision` or `unresolved_comment`).
- **Cluster** related items into common sections to minimize context switching.
- **Prioritize** ordering by deadline, dependency risk, unresolved status, and schedule risk; mark `priority` accordingly.
- **Word agendas concisely** for meeting-ready phrasing (title/description/recommended_outcome).
- **Preserve traceability** by attaching `source_refs` for every agenda, carry-forward, decision, risk, and pre-read entry.
- **Pre-reads**: mark `pre_read_required=true` when the item needs review; include `pre_read_refs` and surface them in `pre_reads`.

## Output formats
- Machine-readable: JSON (`contracts/schemas/meeting_agenda_contract.schema.json`)
- Human-readable: Markdown and DOCX (same content as JSON, rendered for distribution)

## Example artifacts
- **Input mapping**: `contracts/examples/meeting_agenda_input_mapping.json`
- **JSON agenda output**: `contracts/examples/meeting_agenda_contract.json`
- **Markdown agenda output**: `contracts/examples/meeting_agenda_contract.md`

## Operational guidance
- `spectrum-pipeline-engine` may orchestrate this contract by pulling `meeting-minutes-engine` outputs and `comment-resolution-engine` matrices, then emitting agenda artifacts in JSON/Markdown/DOCX using this schema.
- Engines must fail fast if required inputs (`prior_minutes`, `resolution_matrix`) are missing or if `source_refs` are absent on agenda items.
- Use `output_targets` to declare which outputs were emitted (`json`, `markdown`, `docx`); all three are canonical targets.
- Downstream tooling should validate against `meeting_agenda_contract.schema.json` and retain provenance metadata alongside rendered Markdown/DOCX.
