# Canonical Artifact Chain

Meeting Transcript  
↓  
Extracted Issues  
↓  
Categorized Questions  
↓  
Engineering Analysis Requirements  
↓  
Simulation Outputs  
↓  
Study Artifacts  
↓  
Report Sections  
↓  
Final Report

| Stage | Artifact Format | Schema Used | System Responsible |
| --- | --- | --- | --- |
| Meeting Transcript | Structured transcript with speaker turns and timestamps | transcript segmentation schema | Transcript-to-Issue Engine |
| Extracted Issues | Structured issue records with provenance | `issue-schema` | Transcript-to-Issue Engine |
| Categorized Questions | Issue records with categories, owners, and priorities | `issue-schema` | Transcript-to-Issue Engine |
| Engineering Analysis Requirements | Analysis requirement specs and assumptions | `assumption-schema`, requirements schema | Transcript-to-Issue Engine / analysts |
| Simulation Outputs | Data tables, logs, figures | simulation output schema | Modeling toolchain |
| Study Artifacts | Tables, figures, narrative with provenance | `study-output-schema`, `assumption-schema` | Study Artifact Generator |
| Report Sections | Draft report text mapped to sections | report section schema, `study-output-schema` references | Study Artifact Generator / Comment Resolution Engine |
| Final Report | Approved multi-section report with dispositions | report section schema, `comment-schema` links | Comment Resolution Engine / decision authority |

Every system designed in this repository must operate on or extend this artifact chain. Each stage requires defined schemas, checkpoints, and evaluation harnesses to maintain traceability and reproducibility from raw inputs to final reports.
