# Spectrum Study Operating Model

Canonical north-star model for how spectrum studies run across the ecosystem: two interacting loops that keep people aligned and documents advancing. The bridge between the loops is the pair **Engineering Tasks** (what must be done) and **Engineering Outputs** (what the work produces).

## Two Interacting Loops
- **Coordination Loop** — aligns people, decisions, schedules, and next steps so the study stays on track.
- **Document Production Loop** — turns engineering work into reviewed and revised study documents that become the record of decision.
- **Bridge** — **Engineering Tasks** are driven by action items, schedule, study plan, and open questions; **Engineering Outputs** feed working papers, figures, tables, and study artifacts.

## Coordination Loop
Purpose: align the team on who is doing what, by when, and why.

Stages and artifacts:
- roster
- meetings
- transcript
- meeting minutes
- action items
- FAQ
- agenda / agenda slides
- next meeting
- **Engineering Tasks** (handed to the bridge)

## Document Production Loop
Purpose: convert engineering work into governed study documents, keep revisions explicit, and capture adjudication.

Stages and artifacts:
- **Engineering Tasks** (drive the work queue)
- **Engineering Outputs**
- working paper
- compare against last revision
- updated working paper
- agency review
- reviewer comments
- comment resolution matrix
- adjudicated matrix
- updated paper (feeds back into coordination)

## ASCII Architecture Diagram
```
Coordination Loop
[Roster] -> [Meetings] -> [Transcript] -> [Meeting Minutes]
    -> [Action Items / FAQ] -> [Agenda / Next Meeting] -> [Engineering Tasks]

                     Bridge
        [Engineering Tasks] --> [Engineering Outputs]

Document Production Loop
[Engineering Outputs] -> [Working Paper] -> [Compare vs Last Revision]
    -> [Updated Working Paper] -> [Agency Review] -> [Reviewer Comments]
    -> [Comment Resolution Matrix] -> [Adjudicated Matrix] -> [Updated Paper]
                                          ^
                                          |
        (agenda, action items, FAQ, next meeting inputs)
                                          |
                              feedback to Coordination Loop
```

## Repo-to-Loop Mapping
- `spectrum-systems` — governance / constitution for both loops.
- `spectrum-data-lake` — artifact lake, fixtures, historical evidence.
- `meeting-minutes-engine` — Coordination Loop engine.
- `working-paper-review-engine` — Document Production Loop upstream review engine.
- `comment-resolution-engine` — review and adjudication engine.
- `docx-comment-injection-engine` — document update engine.
- `spectrum-pipeline-engine` — orchestration across both loops.
- `spectrum-program-advisor` — intelligence layer across the loops.

## Artifact Class Mapping
- **coordination artifacts**: roster, agenda, transcript, meeting minutes, action items, FAQ, schedule.
- **work artifacts**: engineering outputs, figures, tables, working papers, updated papers.
- **review artifacts**: reviewer comments, comment matrix, adjudicated matrix, review findings, decision records.

The loops operate by transitioning among these artifact classes: coordination artifacts generate **Engineering Tasks**, work artifacts capture **Engineering Outputs** and updated papers, and review artifacts drive adjudication and feed back into the coordination backlog.

## How the Loops Interact
- Coordination Loop produces prioritized **Engineering Tasks** and context that define the work queue.
- Document Production Loop consumes **Engineering Outputs** to evolve working papers and adjudicated matrices.
- Updated papers, comment outcomes, and schedule adjustments flow back to meetings, agendas, FAQs, and action items so coordination stays grounded in the latest study state.
