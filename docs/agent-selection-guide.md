# Agent Selection Guide

This repository is a **system design lab notebook** for automation systems related to spectrum engineering workflows.

Multiple AI agents may be used while developing this project. Each agent has strengths in different phases of work.

This guide explains which agent should be used for each type of task.

The goal is to maintain a consistent workflow:

Design → Repository Updates → Implementation

---------------------------------------------------------------------

# The Three Agents

## Copilot

Copilot is best used for **interactive coding inside files**.

Use Copilot when:

- writing Python scripts
- writing MATLAB utilities
- implementing parsers
- implementing pipelines
- editing existing code
- debugging functions
- writing tests

Copilot behaves like a **pair programmer** and is optimized for small, incremental edits.

Copilot should generally be used inside the `src/` directory.

Example tasks:

- implementing comment_resolution_pipeline.py
- writing data ingestion functions
- creating parsers for spreadsheets
- implementing artifact generation utilities

---------------------------------------------------------------------

## Claude

Claude is best used for **reasoning, analysis, and architecture design**.

Use Claude when:

- analyzing bottlenecks
- reviewing system designs
- synthesizing research
- reviewing long documents
- evaluating architecture decisions
- designing schemas
- proposing workflow improvements

Claude excels at working with long documents and structured reasoning.

Claude should typically be used when editing or reviewing documents in:

docs/

Example tasks:

- identifying high-value bottlenecks
- designing new systems
- reviewing the artifact chain
- proposing schema improvements
- evaluating system failure modes

---------------------------------------------------------------------

## Codex

Codex is best used for **executing structured instructions that modify many files**.

Use Codex when:

- creating repository structures
- generating multiple files
- updating documentation
- creating schemas
- performing large repo updates
- applying structured instructions

Codex behaves like a **repository execution engine**.

Example tasks:

- generating the bottleneck map
- creating system design documents
- updating the systems registry
- creating the data lake strategy
- restructuring directories

---------------------------------------------------------------------

# Recommended Workflow

All development in this repository should follow this sequence.

1. Design the system
2. Update the repository documentation
3. Implement the system in a separate repo

Agent workflow:

Claude → Codex → Copilot

Step 1: System Design  
Agent: Claude

Examples:
- identify bottlenecks
- design workflows
- propose schemas
- review architecture

Step 2: Repository Updates  
Agent: Codex

Examples:
- create new documentation
- update system registries
- add schemas
- expand planning artifacts

Step 3: Implementation  
Agent: Copilot

Examples:
- write Python pipelines
- write MATLAB utilities
- implement data ingestion
- implement parsers

---------------------------------------------------------------------

# Mapping Agents to Repository Areas

docs/  
Preferred agent: Claude or Codex

Claude for reasoning and design work.  
Codex for large documentation updates.


schemas/  
Preferred agent: Claude (design) then Codex (implementation).


workflows/  
Preferred agent: Claude for workflow design.


src/  
Preferred agent: Copilot.


eval/  
Preferred agent: Copilot (tests) or Codex (test scaffolding).


examples/  
Preferred agent: Codex.

---------------------------------------------------------------------

# Example Workflow

Example task: Automating comment resolution.

Step 1  
Use Claude to analyze the comment workflow and identify bottlenecks.

Step 2  
Use Codex to update the repository with the system design and schemas.

Step 3  
Use Copilot to implement the pipeline that processes comment spreadsheets.

---------------------------------------------------------------------

# Design Principle

Use the right tool for the right phase of work.

Claude → reasoning  
Codex → repository changes  
Copilot → code implementation


This separation ensures that systems are designed intentionally before being implemented.

---------------------------------------------------------------------
