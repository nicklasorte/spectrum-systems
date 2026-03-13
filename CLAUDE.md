# CLAUDE.md

Claude Agent Guide for Spectrum Systems

---------------------------------------------------------------------

# Purpose

This document provides instructions for Claude-style reasoning agents working in repositories derived from the Spectrum Systems architecture.

Claude agents should focus on structured reasoning, architecture validation, and design review before any implementation or repository-wide updates occur.

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

---------------------------------------------------------------------
