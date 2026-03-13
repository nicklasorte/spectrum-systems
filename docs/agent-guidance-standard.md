# AI Agent Guidance Standard

## Overview

All repositories derived from the Spectrum Systems architecture should include standardized AI-agent guidance files.

These files allow AI systems to correctly interpret repository structure and development workflows.

The standard currently includes:

CLAUDE.md  
CODEX.md

Additional files may be added in the future if needed.

---------------------------------------------------------------------

## CLAUDE.md

### Purpose

Provides guidance to reasoning agents.

Typical responsibilities include:

- architecture reasoning
- system design analysis
- document review
- schema design evaluation
- workflow reasoning

CLAUDE.md should describe:

- repository purpose
- architectural philosophy
- design constraints
- reasoning tasks appropriate for Claude

---------------------------------------------------------------------

## CODEX.md

### Purpose

Provides guidance to repository execution agents.

Typical responsibilities include:

- creating files
- updating repository structure
- applying structured instructions
- generating schemas
- updating documentation

CODEX.md should describe:

- repository editing rules
- schema creation guidelines
- documentation update expectations
- multi-file update practices

---------------------------------------------------------------------

## Agent Workflow

Repositories derived from this architecture should typically follow this workflow:

Claude → reasoning and architecture  
Codex → repository updates  
Copilot → code implementation

---------------------------------------------------------------------
