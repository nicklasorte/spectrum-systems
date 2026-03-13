# Transcript-to-Issue Engine (SYS-002)

Purpose: convert meeting transcripts into structured issues with clear owners, priorities, and provenance.

- **Bottleneck**: BN-002 — actions and blockers remain buried in transcripts and get lost between meetings.
- **Inputs**: Meeting transcripts with speaker/timestamp metadata, participant roles, meeting context, prior backlog for linkage.
- **Outputs**: Structured issue records with category, priority, owner, status, provenance, and run manifest references.
- **Upstream Dependencies**: Transcript capture, speaker identity metadata, prompt/rule versions.
- **Downstream Consumers**: Issue backlog, assumption registry, decision artifacts.
- **Related Assets**: `schemas/issue-schema.json`, `prompts/transcript-to-issue.md`, `eval/transcript-to-issue`.
- **Lifecycle Status**: Design complete; prompts need ongoing hardening (`docs/system-status-registry.md`).
