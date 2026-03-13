# System Planning Framework for Spectrum Automation Systems

## Overview
This document defines the standard planning process used before building any automated system or AI-assisted workflow in the spectrum-systems repository. These steps ensure that systems are designed intentionally and are reproducible, testable, and maintainable.

## STEP 1 - Identify the highest-value bottlenecks
Survey the system and identify recurring tasks that consume expert time or slow decision-making. Focus on tasks that are repetitive, high-impact, and currently performed manually.

## STEP 2 - Separate root bottlenecks from surface symptoms
Determine whether a problem is the actual constraint or merely a downstream symptom. For example, slow report writing may actually be caused by missing structured artifacts earlier in the workflow.

## STEP 3 - Define the system boundaries
Explicitly define what the system will do and what it will not do. Specify the scope of the workflow being automated.

Define:
- Inputs
- Processing stages
- Decisions
- Outputs
- Human review stages

## STEP 4 - Choose one wedge problem
Do not attempt to automate everything at once. Select a single high-impact workflow to automate first. The goal is to create an initial system that demonstrates value and establishes architectural patterns.

## STEP 5 - Define the input schemas
Before writing code, formally define the structure of the data that enters the system. Examples include comment schemas, issue schemas, assumptions, study outputs, and precedent cases.

## STEP 6 - Define the canonical artifact chain
Design the sequence of artifacts generated throughout the workflow.

Example:
- meeting transcript
- extracted issues
- categorized questions
- required analyses
- engineering outputs
- report-ready text

Each artifact must be reusable by downstream systems.

## STEP 7 - Determine where AI should be used
Identify which parts of the workflow are suitable for AI assistance.

Good candidates include:
- classification
- extraction
- summarization
- draft generation
- knowledge retrieval

Human judgment should remain responsible for final decisions and validation.

## STEP 8 - Design human review checkpoints
Define where human experts must review or approve system outputs.

Examples:
- engineering validation
- policy review
- final report approval

## STEP 9 - Create evaluation harnesses
Design test inputs and expected outputs that allow the system to be evaluated objectively. Evaluation harnesses allow the system to be improved without breaking existing workflows.

## STEP 10 - Build the institutional memory layer
Store outputs and resolved examples so that the system learns from prior work. Examples include resolved comments, precedent cases, validated assumptions, and prior studies.

## STEP 11 - Design outputs to be report-ready
Systems should generate structured artifacts such as tables, figures, summaries, and report-ready text sections rather than only raw analytical data.

## STEP 12 - Use modular architecture
Structure the system as modular components:
- ingestion
- normalization
- analysis
- synthesis
- validation
- export

Modules should be replaceable and independently testable.

## STEP 13 - Document the house method
Document the standard methodology used by the system including default assumptions, analysis methods, validation checks, and output formats.

## STEP 14 - Build a ranked roadmap
Prioritize future systems according to impact, feasibility, reuse potential, and dependencies.

## STEP 15 - Protect dedicated system-building time
Automation systems require sustained development effort. Ensure time is allocated specifically for designing and improving the systems rather than only performing manual analysis.

## Conclusion
All automation systems in this repository must be designed using these 15 planning steps before implementation begins.
