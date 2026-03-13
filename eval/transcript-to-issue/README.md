# Transcript-to-Issue Evaluation

## Purpose
Assess how well the Transcript-to-Issue Engine converts meeting transcripts into prioritized, structured issue records with traceability.

## Test Inputs
- Meeting transcripts with varied speakers and topics
- Context prompts and participant metadata
- Known issue labels for comparison

## Expected Outputs
- Structured issue records aligned to `issue-schema`
- Categorization and status for each issue
- Populated traceability fields for source_document and source_location
- Run manifest reference for reproducibility checks

## Evaluation Criteria
- Precision and recall of extracted issues against a labeled set
- Correct categorization and status assignment
- Completeness of traceability metadata and timestamps
- Determinism of outputs given identical transcripts and prompts

## Failure Modes
- Missed or merged issues that reduce recall
- Incorrect categorization or status values
- Missing or incorrect source locations
- Variability in outputs across repeated runs
