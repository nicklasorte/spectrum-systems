# Working Paper Generator — Design

## Purpose

The `working_paper_generator` module turns meeting transcripts, meeting
minutes, and an optional existing draft working paper into structured
working-paper artifacts that help groups move from discussion to shared
written understanding.

The module bridges the gap between conversational output (transcripts, informal
minutes) and formal written records (working papers, technical reports, policy
documents).

---

## Problem Statement

Spectrum engineering working groups regularly discuss contested topics in
meetings but struggle to translate that discussion into written progress.
Key symptoms:

- Decisions made verbally are not captured in the working paper.
- Open questions accumulate across meeting cycles without being tracked.
- Reviewers cannot tell which sections are ready to be finalised.
- The same arguments are re-litigated because they were never written down.

The working paper generator addresses these symptoms deterministically from
structured inputs.

---

## System Context

| Upstream inputs | Downstream consumers |
|---|---|
| Meeting transcript (plain text) | Updated working paper draft (JSON / Markdown) |
| Meeting minutes (optional) | Open question register |
| Existing working paper draft (optional) | Readiness assessment |
| | Argument registry |

The module is a **workflow module** in the `spectrum-systems` classification
and depends on the shared layer for artifact envelope and provenance models.

---

## Processing Pipeline

```
Transcript ──────────────────────┐
Minutes (optional) ──────────┐   │
Existing draft (optional) ──┐│   │
                             ││   │
                        ┌────▼▼───▼────────────────────────────────┐
                        │         working_paper_generator           │
                        │                                           │
                        │  1. transcript_parser                     │
                        │  2. paper_state_reader                    │
                        │  3. meeting_delta_engine                  │
                        │  4. argument_builder                      │
                        │  5. question_engine                       │
                        │  6. readiness_scorer                      │
                        │  7. patch_generator                       │
                        │  8. draft_writer                          │
                        └───────────────────────────────────────────┘
                                          │
                         ┌────────────────┴──────────────────┐
                         ▼                                   ▼
                  WorkingPaperDraft               CLI stdout / file
                  (JSON artifact)                  (JSON or Markdown)
```

### Step descriptions

1. **transcript_parser** — Parse raw transcript text into `ParsedTranscript`
   with typed `TranscriptSegment` objects.  Supports bracket-speaker
   (`[Speaker]`), timestamped-bracket, and colon-speaker (`Speaker: text`)
   formats.  Tags segments as `action`, `question`, or `decision` based on
   keyword heuristics.

2. **paper_state_reader** — Read an existing working paper from a `.json` file
   (structured) or plain-text / Markdown file (heading-delimited).  Returns a
   `PaperState` with typed `PaperSection` objects.

3. **meeting_delta_engine** — Compute a `MeetingDelta` by comparing the
   transcript against the existing paper state.  Identifies new topics, which
   sections were discussed, unresolved questions, and consensus items.

4. **argument_builder** — Extract `Argument` objects with claim, evidence,
   speaker attribution, stance (`supporting` / `opposing` / `neutral`), and
   optional section reference.

5. **question_engine** — Identify `OpenQuestion` objects from segments
   containing `?`, explicit marker phrases, or `question` tags.  Infer
   resolution status by looking ahead for answer cues from other speakers.

6. **readiness_scorer** — Score each paper section on a `[0.0, 1.0]` scale
   using three components:
   - **coverage** (0.5 weight): fraction of open issues addressed by meeting
   - **consensus** (0.3 weight): fraction of consensus items referencing this section
   - **question_penalty** (−0.2 weight): unresolved open questions for this section

   A section is ready-to-draft when score ≥ 0.5.  The paper is ready-to-draft
   when ≥ 60 % of sections are ready.

7. **patch_generator** — Generate a `PaperPatch` with `update` operations for
   sections discussed in the meeting and `add` operations for new topics not
   represented in existing sections.

8. **draft_writer** — Apply the patch to the existing paper state (or scaffold
   from scratch) and assemble a `WorkingPaperDraft` combining sections,
   arguments, questions, and the readiness report.

---

## Data Models

All data models are pure Python `dataclass` objects defined in `schemas.py`.
They serialise to/from plain dicts and are not coupled to any persistence layer.

| Model | Role |
|---|---|
| `TranscriptSegment` | Single utterance with speaker, timestamp, text, tags |
| `ParsedTranscript` | Collection of segments + participant list |
| `PaperSection` | Section with id, title, content, status, open issues |
| `PaperState` | Full paper: id, title, version, sections |
| `MeetingDelta` | New topics, updated section ids, unresolved/consensus items |
| `Argument` | Claim + evidence + speaker + stance + section ref |
| `OpenQuestion` | Question text + raised-by + section ref + resolution status |
| `SectionReadiness` | Per-section score, rationale, blocking questions |
| `ReadinessReport` | Overall score, section scores, ready-to-draft flag |
| `SectionPatch` | One proposed change (add/update/delete) to a section |
| `PaperPatch` | Collection of `SectionPatch` objects for a meeting |
| `WorkingPaperDraft` | Final output artifact |

---

## CLI

```
scripts/run_working_paper_generator.py
```

| Flag | Required | Description |
|---|---|---|
| `--transcript PATH` | ✅ | Path to meeting transcript (plain text) |
| `--minutes PATH` | ❌ | Optional meeting minutes file |
| `--draft PATH` | ❌ | Optional existing working paper draft (JSON or Markdown) |
| `--output PATH` | ❌ | Output file path (default: stdout) |
| `--format json\|markdown` | ❌ | Output format (default: json) |
| `--meeting-title TITLE` | ❌ | Meeting title for attribution (default: "Meeting") |

---

## Evaluation Criteria

| Criterion | Test |
|---|---|
| All module files are present | `test_module_files_exist` |
| Transcript parser handles multiple speaker formats | `test_parse_transcript_*` |
| Paper state reader handles JSON and plain text | `test_read_paper_state_*` |
| Delta engine identifies consensus and unresolved items | `test_compute_delta_*` |
| Argument builder assigns valid stances | `test_build_arguments_*` |
| Question engine detects questions and infers resolution | `test_extract_questions_*` |
| Readiness scorer produces scores in [0.0, 1.0] | `test_score_readiness_*` |
| Patch generator emits add/update operations | `test_generate_patch_*` |
| Draft writer applies patches and increments version | `test_write_draft_*` |
| CLI: help, JSON, Markdown, draft input, missing flag | `test_cli_*` |

---

## Failure Modes

| Input condition | Behaviour |
|---|---|
| Empty transcript | Returns `ParsedTranscript` with no segments; pipeline proceeds with empty delta |
| No existing draft | Pipeline scaffolds sections from new topics only |
| Malformed JSON draft | Falls back to plain-text parser |
| No decisions/questions in transcript | Scores will be 0.0; draft is created but `ready_to_draft=False` |

---

## Boundaries and Forbidden Responsibilities

This module **must not**:

- Define `ArtifactEnvelope` or provenance schemas — those belong to `shared.artifact_models`.
- Implement comment resolution logic — that belongs to `workflow_modules.comment_resolution`.
- Perform lifecycle enforcement or governance — that belongs to `control_plane`.
- Define identifier schemes — those belong to `shared.ids`.
- Store or query domain regulatory data — that belongs to `domain_modules`.

---

## Implementation Notes

- All processing is deterministic given the same inputs; no LLM calls are made.
- The module is designed as a **reference scaffold** to be consumed by a
  downstream implementation repository.  That repository must import contracts
  from `spectrum-systems` and must not redefine shared-truth structures.
- The `schemas.py` data classes should eventually wrap `ArtifactEnvelope` from
  `shared.artifact_models` in a production deployment.

---

## Related Systems

| System | Relationship |
|---|---|
| `meeting-minutes-engine` (SYS-006) | Upstream: produces meeting minutes consumed here |
| `working-paper-review-engine` (SYS-007) | Downstream: consumes the working paper draft |
| `comment-resolution` | Downstream: ingests open questions as potential comments |
| `spectrum-program-advisor` | Downstream: incorporates readiness assessment into program briefs |
