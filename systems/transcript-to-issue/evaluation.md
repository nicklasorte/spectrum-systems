# Evaluation Plan — Transcript-to-Issue Engine

Evaluation assets live in `eval/transcript-to-issue`.

- **Objectives**: Measure extraction recall/precision, correctness of categorization/priority/owner, and provenance completeness.
- **Datasets/Fixtures**: Labeled transcripts with speaker/timestamp metadata and known issues/action items.
- **Metrics**: Issue-level precision/recall, category accuracy, owner accuracy, provenance completeness, run-to-run stability.
- **Blocking Failures**: Missing speaker/timestamp, schema violations, inconsistent outputs with identical manifests.
- **Traceability**: Every issue must carry meeting ID, timestamp, speaker, and run manifest reference (`docs/reproducibility-standard.md`).
- **Review**: Low-confidence items must be routed to human review; evaluation should confirm routing is triggered.
