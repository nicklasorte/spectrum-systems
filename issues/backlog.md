# Backlog

| Priority | System | Description | Dependencies | Status |
| --- | --- | --- | --- | --- |
| 1 | Comment Resolution Engine | Structure comments, map to sources, and generate disposition drafts with traceability. | comment-schema, prompt-standard, artifact-chain, eval/comment-resolution | Design |
| 2 | Transcript-to-Issue Engine | Convert meeting transcripts into prioritized issues with categorization and provenance. | issue-schema, prompt-standard, artifact-chain, eval/transcript-to-issue | Design |
| 3 | Study Artifact Generator | Transform simulations into structured artifacts and report-ready sections. | study-output-schema, assumption-schema, artifact-chain, eval/study-artifact | Design |
| 4 | Spectrum Decision Engine | Aggregate analyses and precedents to produce decision briefs and tradeoff matrices. | precedent-schema, study-output-schema, artifact-chain | Design |
| 5 | Institutional Knowledge Engine | Capture and retrieve institutional memory across studies, comments, and decisions. | precedent-schema, issue-schema, assumption-schema, artifact-chain | Design |
