# CLAUDE.md

Claude Agent Guide for Spectrum Systems

---------------------------------------------------------------------

# Purpose

This document provides instructions for Claude-style reasoning agents working in repositories derived from the Spectrum Systems architecture.

Claude agents should focus on structured reasoning, architecture validation, and design review before any implementation or repository-wide updates occur.
AI Agent Guide for Spectrum Systems Lab Notebook

---------------------------------------------------------------------

# Purpose of This Repository

This repository is a **system design lab notebook** for developing automation systems related to spectrum engineering workflows.

It is intentionally **design-first and documentation-first**.

This repository should contain:

- system design documents
- bottleneck analysis
- workflow descriptions
- schema definitions
- data lake strategy
- provenance standards
- research questions
- planning artifacts

This repository should **NOT contain production implementation code**.

Implementation systems should be built in **separate repositories**.

---------------------------------------------------------------------

# Core Design Philosophy

The goal of this repository is to identify leverage points in complex engineering workflows and design automation systems that improve those workflows.

The design approach follows this sequence:

1. Identify bottlenecks
2. Design automation systems
3. Define required data structures
4. Define workflows
5. Define provenance and traceability
6. Implement systems in separate repos

This repository focuses on **steps 1–5**.

---------------------------------------------------------------------

# Agent Workflow

Different AI agents should be used for different types of tasks.

Claude → reasoning and architecture design  
Codex → repository modifications  
Copilot → code implementation in other repos

Use the appropriate agent for each phase.

---------------------------------------------------------------------

# Claude Responsibilities

Claude should primarily be used for high-leverage reasoning tasks such as:

- architecture reasoning and system design
- workflow analysis and improvement
- schema evaluation and design critique
- long-form document review and synthesis
- risk assessment and assumption validation

Claude operates as the **reasoning and design agent** for this architecture.

---------------------------------------------------------------------

# Interaction With Other Agents

Development should follow this workflow:

Claude → reasoning and design  
Codex → repository updates  
Copilot → code implementation

Claude should provide the design decisions and constraints that Codex and Copilot execute against.

---------------------------------------------------------------------

# Agent Guidance Standard

All repositories derived from the Spectrum Systems architecture should include standardized AI agent guidance files.

Required files:

CLAUDE.md  
CODEX.md  

Purpose:

CLAUDE.md provides instructions for reasoning agents.  
CODEX.md provides instructions for repository execution agents.

These files help AI agents understand:

- repository purpose
- architectural boundaries
- allowed modifications
- workflow expectations
Claude should be used for:

- reasoning about architecture
- identifying bottlenecks
- reviewing system designs
- analyzing documents
- proposing schema designs
- evaluating workflow logic
- performing clarity reviews of the repository

Claude should generally work with documents in:

docs/

Claude should not create large numbers of files directly.

Instead, Claude should produce structured instructions that Codex executes.

---------------------------------------------------------------------

# Codex Responsibilities

Codex should be used for:

- creating repository structure
- generating documentation files
- applying large structured changes
- creating schemas
- updating multiple documents
- restructuring directories

Codex acts as the **execution engine** for repository updates.

---------------------------------------------------------------------

# Copilot Responsibilities

Copilot should be used in implementation repositories for:

- writing code
- implementing pipelines
- writing MATLAB utilities
- writing Python scripts
- building data ingestion pipelines
- building automation systems

Copilot should generally work inside:

src/

This repository intentionally does not include a src directory.

---------------------------------------------------------------------

# Repository Structure

Root structure:

docs/  
Architecture documents and design artifacts.

schemas/  
Schema definitions for structured data.

issues/  
Backlog and research questions.

workflows/  
Conceptual workflow definitions.

examples/  
Illustrative artifacts.

---------------------------------------------------------------------

# Key Design Documents

Important documents in this repository include:

bottleneck-map.md  
Identifies high-value leverage points in current workflows.

systems-registry.md  
Catalog of proposed automation systems.

data-lake-strategy.md  
Defines the structured data foundation for automation systems.

data-provenance-standard.md  
Defines the traceability model for all data and artifacts.

agent-selection-guide.md  
Explains when to use Copilot, Claude, or Codex.

---------------------------------------------------------------------

# Design Principles

Automation systems should prioritize:

- traceability
- reproducibility
- clarity
- structured data
- provenance
- human review

AI-assisted outputs must always support human verification.

---------------------------------------------------------------------

# Provenance Requirement

All schemas and data structures should eventually support the provenance standard defined in:

docs/data-provenance-standard.md

Important artifacts should record:

- source
- derivation
- generating workflow
- version
- human review status
- confidence level

---------------------------------------------------------------------

# Editing Guidelines for AI Agents

When updating this repository:

1. Preserve the documentation-first philosophy.
2. Do not introduce production code.
3. Maintain conceptual consistency across documents.
4. Link new concepts to existing systems and bottlenecks.
5. Prefer clarity over complexity.

If a change would significantly alter the architecture, propose the change first rather than applying it automatically.

---------------------------------------------------------------------
