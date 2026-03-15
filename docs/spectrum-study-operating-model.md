# Spectrum Study Operating Model

Canonical north-star model for how spectrum studies run across the ecosystem: two interacting loops that keep people aligned and documents advancing. The bridge between the loops is the pair **Engineering Tasks** (what must be done) and **Engineering Outputs** (what the work produces).

## Two Interacting Loops
- **Coordination Loop** — aligns people, decisions, schedules, and next steps so the study stays on track and generates the engineering work.
- **Document Production Loop** — turns engineering work into reviewed and revised study documents that become the record of decision.
- **Bridge** — split “engineering work” into **Engineering Tasks** and **Engineering Outputs** so each loop can hand off and accept work deterministically.

## Coordination Loop
Purpose: align the team on who is doing what, by when, and why; produce the next wave of **Engineering Tasks**.

Stages and artifacts:
- roster
- meetings
- transcript
- meeting minutes
- action items
- FAQ
- agenda / agenda slides
- next meeting
- **Engineering Tasks** (emitted to the bridge and prioritized in the work queue)

## Document Production Loop
Purpose: convert engineering work into governed study documents, keep revisions explicit, and capture adjudication that feeds future meetings.

Stages and artifacts:
- **Engineering Tasks** (drive the work queue)
- **Engineering Outputs**
- working paper
- compare with previous revision
- updated working paper
- agency review
- reviewer comments
- comment resolution matrix
- adjudicated matrix
- updated paper (feeds back into coordination)

## Bridge Between Loops
- **Engineering Tasks** come from action items, the study plan, schedule, and open questions in the Coordination Loop.
- **Engineering Outputs** produce figures, tables, analysis artifacts, and working paper revisions that the Document Production Loop consumes.
- The bridge keeps a clear interface: coordination creates tasks; production returns outputs that inform agendas, FAQs, and action items.

## ASCII Architecture Diagram
```
Coordination Loop
[Roster] -> [Meetings] -> [Transcript] -> [Meeting Minutes]
    -> [Action Items] -> [FAQ] -> [Agenda / Slides] -> [Next Meeting]
                               \                     /
                                \-> [Engineering Tasks]

                   Bridge
        [Engineering Tasks] --> [Engineering Outputs]

Document Production Loop
[Engineering Outputs] -> [Working Paper] -> [Compare w/ Previous Revision]
    -> [Updated Working Paper] -> [Agency Review] -> [Reviewer Comments]
    -> [Comment Resolution Matrix] -> [Adjudicated Matrix] -> [Updated Paper]
                                          ^                       |
                                          |                       |
                     (agendas, action items, FAQs, next meeting updates)
                                          |
                               feedback to Coordination Loop
```

## Repo-to-Loop Mapping
- `spectrum-systems` — governance and contract definitions for both loops.
- `spectrum-data-lake` — artifact lake for transcripts, minutes, working papers, and review artifacts.
- `meeting-minutes-engine` — Coordination Loop engine.
- `working-paper-review-engine` — generates reviewer comment sets from working papers.
- `comment-resolution-engine` — produces adjudicated comment matrices.
- `docx-comment-injection-engine` — applies adjudicated comments to working papers.
- `spectrum-pipeline-engine` — runs end-to-end workflows across both loops.
- `spectrum-program-advisor` — analyzes artifacts and pipeline reports to recommend improvements.

## Artifact Class Mapping
- **coordination artifacts**: roster, agenda, transcript, meeting minutes, action items, FAQ.
- **work artifacts**: engineering outputs, figures, tables, working papers.
- **review artifacts**: review comments, comment matrices, adjudicated matrices.

The loops operate by transitioning among these artifact classes: coordination artifacts generate **Engineering Tasks**; work artifacts capture **Engineering Outputs** and updated papers; review artifacts drive adjudication and feed back into the coordination backlog.

## How the Loops Interact
- Coordination Loop produces prioritized **Engineering Tasks** and context that define the work queue.
- Document Production Loop consumes **Engineering Outputs** to evolve working papers and adjudicated matrices.
- Updated papers, comment outcomes, and schedule adjustments flow back to meetings, agendas, FAQs, and action items so coordination stays grounded in the latest study state.
