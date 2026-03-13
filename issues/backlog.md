# Backlog

| Priority | System | Description | Dependencies | Status |
| --- | --- | --- | --- | --- |
| 1 | Comment Resolution Engine | Structure multi-agency comments, map to report sections, and draft traceable dispositions. | comment-schema, prompt-standard, artifact-chain, eval/comment-resolution | Design Specification |
| 2 | Transcript-to-Issue Engine | Convert meeting transcripts into prioritized, categorized issues with provenance. | issue-schema, prompt-standard, artifact-chain, eval/transcript-to-issue | Design Specification |
| 3 | Study Artifact Generator | Transform simulations into structured artifacts and report-ready sections with provenance. | study-output-schema, assumption-schema, artifact-chain, eval/study-artifacts | Design Specification |
| 4 | Spectrum Decision Engine | Aggregate analyses and precedents to produce decision briefs and tradeoff matrices. | precedent-schema, study-output-schema, artifact-chain | Design |
| 5 | Institutional Knowledge Engine | Capture and retrieve institutional memory across studies, comments, and decisions. | precedent-schema, issue-schema, assumption-schema, artifact-chain | Design |
| 6 | Data Lake | Design initial data lake schemas. | data-lake-strategy, schemas/data-lake | New |
| 7 | Data Lake | Define provenance rules across data classes. | data-lake-strategy, data-class-registry | New |
| 8 | Data Lake | Link system designs to required data classes. | systems-registry, data-class-registry | New |
| 9 | Data Lake | Create first sample data assets for Tier 1 data classes. | schemas/data-lake, data-lake-strategy | New |
