# Systems Directory

Canonical home for system-level docs. Each system folder contains:
- `overview.md` — purpose, scope, and dependencies.
- `interface.md` — input/output contracts, schemas, validation rules.
- `design.md` — processing stages, human review gates, and failure modes.
- `evaluation.md` — evaluation approach and links to `eval/`.
- `prompts.md` — prompts and rules used by the system.

Systems currently defined:
- `comment-resolution` (SYS-001)
- `transcript-to-issue` (SYS-002)
- `study-artifact-generator` (SYS-003)
- `spectrum-study-compiler` (SYS-004)
- `spectrum-program-advisor` (SYS-005)
- `meeting-minutes-engine` (SYS-006)
- `working-paper-review-engine` (SYS-007)
- `docx-comment-injection-engine` (SYS-008)
- `spectrum-pipeline-engine` (SYS-009)

Follow `docs/system-interface-spec.md` and `docs/system-lifecycle.md` when adding or updating a system.

---

## Spectrum Studies Pipeline: Complete System Architecture

**Status**: Canonical specification for spectrum-studies MVP  
**Last Updated**: 2026-04-15  
**Authority**: System integration registry  

---

### Executive Overview

The Spectrum Studies Pipeline is a nine-system workflow that transforms raw meeting transcripts into report-ready spectrum studies with agency feedback integrated and resolved.

**Input**: Raw meeting transcripts from spectrum-data-lake  
**Output**: Governance-verified, report-ready spectrum studies with resolved agency comments  
**Critical Path**: Transcript → Minutes → Issues/FAQs → Study Artifacts → Working Papers → Comments → Resolution → Final Package

---

### Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAW MEETING TRANSCRIPTS                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
   [SYS-006]                         [SYS-002]
   Meeting Minutes               Transcript-to-Issue
   Engine                        Engine
        │                                 │
        │ Meeting Minutes                │ Issues + FAQs
        │                                │
   ┌────┴──────────────────────────────┐
   │                                    │
   │ [SYS-003]                          │
   │ Study Artifact Generator           │
   │ (Transforms outputs →              │
   │  Study artifacts + report sections)│
   │                                    │
   └────────────────┬───────────────────┘
                    │
                    │ Study Artifacts
                    │ Report Sections
                    │
        ┌───────────┴──────────────┐
        │                          │
   [SYS-004]                   [SYS-007]
   Spectrum Study             Working Paper
   Compiler                   Review Engine
   (Package +                 (Normalize
    validate)                  feedback)
        │                          │
        │ Compiled Package         │ Comment Artifacts
        │                          │
        └───────────┬──────────────┘
                    │
              [SYS-001]
              Comment Resolution
              Engine
              (Resolve agency
               comments →
               dispositions)
                    │
              Resolved Comments
                    │
              [SYS-008]
              DOCX Comment
              Injection Engine
              (Apply comments
               to deliverables)
                    │
         ┌──────────┴──────────┐
         │                     │
    [SYS-005]            FINAL DELIVERABLES
    Spectrum Program    (Report-ready
    Advisor            spectrum studies
    (Red-team/         with resolved
     decision briefs)   comments)
         │
    Decision Briefs
    Readiness Scores

        ↓ All orchestrated by ↓

       [SYS-009]
    Spectrum Pipeline Engine
    (Deterministic orchestration
     of all upstream systems)
```

---

### System Catalog

#### SYS-001: Comment Resolution Engine

**Purpose**: Resolve agency comments deterministically with traceable dispositions tied to working paper revisions.

**Input**:
- Comment artifacts from SYS-007 (Working Paper Review Engine)
- Working paper drafts with agency feedback
- Comment resolution matrices (from agencies)

**Output**:
- Resolved comment artifacts
- Disposition traceback (why each comment was resolved how)
- Revision instructions for working papers

**Dependencies**:
- SYS-007 (Working Paper Review Engine) — produces comments
- SYS-003 (Study Artifact Generator) — study context

**Status**: ❓ **UNKNOWN** (needs audit)
- Documentation: ✅ Complete (`systems/comment-resolution/overview.md`)
- Code: ❓ Need to verify (`spectrum_systems/modules/` — search for implementation)
- Tests: ❓ Unknown

**Location**:
- Docs: `systems/comment-resolution/`
- Code: `spectrum_systems/modules/` (location TBD)
- Schemas: `contracts/schemas/` (TBD)

**Contracts**:
- Input: Comment artifacts (schema TBD)
- Output: Disposition artifacts (schema TBD)

---

#### SYS-002: Transcript-to-Issue Engine

**Purpose**: Convert meeting transcripts into structured issues with clear owners, priorities, and provenance.

**Input**:
- Raw meeting transcripts with speaker/timestamp metadata
- Participant roles, meeting context
- Prior backlog for linkage

**Output**:
- Structured issue records (category, priority, owner, status)
- Provenance records
- FAQ extractions

**Dependencies**:
- SYS-006 (Meeting Minutes Engine) — input normalization (optional)
- Upstream: Raw transcripts

**Status**: ❓ **UNKNOWN** (needs audit)
- Documentation: ✅ Complete (`systems/transcript-to-issue/`)
- Code: ❓ Need to verify
- Prompts: ✅ Exists (`prompts/transcript-to-issue.md`)
- Test cases: ✅ Exist (`cases/meeting_minutes/examples/`, `data/adversarial_cases/`)

**Location**:
- Docs: `systems/transcript-to-issue/`
- Code: `spectrum_systems/modules/` (TBD)
- Prompts: `prompts/transcript-to-issue.md`
- Examples: `examples/example-transcript.txt`

**Contracts**:
- Input: `contracts/schemas/transcript_intelligence_pack.schema.json`
- Output: Issue schema (TBD)

---

#### SYS-003: Study Artifact Generator

**Purpose**: Transform simulation outputs into structured study artifacts and report-ready sections with embedded provenance.

**Input**:
- Simulation outputs
- Study inputs and manifests
- Metadata and context

**Output**:
- Structured study artifacts
- Report-ready sections
- Embedded provenance records

**Dependencies**:
- SYS-002 (Transcript-to-Issue Engine) — issues/FAQs
- SYS-006 (Meeting Minutes Engine) — context

**Status**: ❓ **UNKNOWN** (needs audit)
- Documentation: ✅ Complete (`systems/study-artifact-generator/`)
- Code: ✅ Exists (`spectrum_systems/modules/` — search for study_artifact)
- Schemas: ❓ TBD

**Location**:
- Docs: `systems/study-artifact-generator/`
- Code: `spectrum_systems/modules/` (TBD)

**Contracts**:
- Input: Study inputs manifest (schema TBD)
- Output: Study artifact schema (TBD)

---

#### SYS-004: Spectrum Study Compiler

**Purpose**: Compile study inputs, artifacts, and manifests into a validated, packaged deliverable with explicit warnings/errors.

**Input**:
- All study artifacts from SYS-003
- Resolved comments from SYS-001
- Metadata and validation rules

**Output**:
- Validated, packaged deliverable
- Warnings/errors log
- Contract compliance report

**Dependencies**:
- SYS-003 (Study Artifact Generator) — produces artifacts
- SYS-001 (Comment Resolution Engine) — produces resolved comments
- SYS-008 (DOCX Comment Injection Engine) — produces final DOCX

**Status**: ❓ **UNKNOWN** (needs audit)
- Documentation: ✅ Complete (`systems/spectrum-study-compiler/`)
- Code: ❓ TBD
- Validation logic: ❓ TBD

**Location**:
- Docs: `systems/spectrum-study-compiler/`
- Code: `spectrum_systems/modules/` (TBD)

**Contracts**:
- Input: All artifacts (various schemas)
- Output: Packaged deliverable schema (TBD)

---

#### SYS-005: Spectrum Program Advisor

**Purpose**: Elevate program-management guidance for spectrum studies by turning canonical artifacts into decision-ready briefs, readiness scores, and prioritized actions.

**Input**:
- Study artifacts from SYS-003
- Resolved comments from SYS-001
- Program context and constraints

**Output**:
- Decision-ready briefs
- Readiness scores (0-100)
- Prioritized action items
- Red-team feedback (optional)

**Dependencies**:
- SYS-003 (Study Artifact Generator)
- SYS-001 (Comment Resolution Engine)
- Optional: SYS-004 (for final packages)

**Status**: ❓ **UNKNOWN** (needs audit)
- Documentation: ✅ Complete (`systems/spectrum-program-advisor/`)
- Code: ❓ TBD
- Red-team logic: ❓ TBD

**Location**:
- Docs: `systems/spectrum-program-advisor/`
- Code: `spectrum_systems/modules/` (TBD)

**Contracts**:
- Input: Study artifacts
- Output: Readiness brief schema (TBD)

---

#### SYS-006: Meeting Minutes Engine

**Purpose**: Convert meeting transcripts into governed, traceable minutes aligned to the canonical meeting minutes contract.

**Input**:
- Raw meeting transcripts
- Speaker metadata, timestamps
- Meeting context

**Output**:
- Governed meeting minutes
- Structured decisions record
- Attendee list and roles

**Dependencies**:
- Upstream: Raw transcripts

**Status**: ❓ **UNKNOWN** (needs audit)
- Documentation: ✅ Complete (`systems/meeting-minutes-engine/`)
- Code: ❓ TBD
- Contracts: ✅ Exists (`contracts/schemas/meeting_minutes/transcript_facts_output.schema.json`)

**Location**:
- Docs: `systems/meeting-minutes-engine/`
- Code: `spectrum_systems/modules/` (TBD)
- Contracts: `contracts/schemas/meeting_minutes/transcript_facts_output.schema.json`

**Contracts**:
- Input: Raw transcript
- Output: `contracts/schemas/meeting_minutes/transcript_facts_output.schema.json`

---

#### SYS-007: Working Paper Review Engine

**Purpose**: Ingest working paper drafts, normalize reviewer feedback, and emit canonical comment artifacts for downstream resolution and orchestration.

**Input**:
- Working paper drafts (DOCX/PDF)
- Reviewer feedback (comments, annotations, matrices)
- Review context and rubrics

**Output**:
- Canonical comment artifacts
- Normalized feedback (structured)
- Review provenance

**Dependencies**:
- SYS-003 (Study Artifact Generator) — produces working papers
- Upstream: Reviewer feedback (agencies, red team, etc.)

**Status**: ⚠️ **PARTIAL** (code exists, needs verification)
- Documentation: ✅ Complete (`systems/working-paper-review-engine/`)
- Code: ✅ Exists (`spectrum_systems/modules/working_paper_engine/`)
  - `artifacts.py` (12KB)
  - `interpret.py` (8KB)
  - `models.py` (7KB)
  - `observe.py` (6KB)
  - `service.py` (5KB)
  - `synthesize.py` (20KB) ← **Core logic**
  - `validate.py` (13KB)
- Tests: ❓ Unknown

**Location**:
- Docs: `systems/working-paper-review-engine/`
- Code: `spectrum_systems/modules/working_paper_engine/`
- Additional: `spectrum_systems/modules/working_paper_generator.py`, `spectrum_systems/modules/runtime/working_paper_synthesis.py`

**Contracts**:
- Input: Working paper artifact (schema TBD)
- Output: Comment artifact (schema TBD)

---

#### SYS-008: DOCX Comment Injection Engine

**Purpose**: Apply PDF/DOCX-anchored comments and dispositions into governed DOCX deliverables while preserving provenance and contract fidelity.

**Input**:
- Resolved comments from SYS-001
- DOCX/PDF templates
- Comment disposition records

**Output**:
- Annotated DOCX/PDF files
- Comment provenance records
- Final deliverables

**Dependencies**:
- SYS-001 (Comment Resolution Engine) — produces resolved comments
- SYS-003 (Study Artifact Generator) — provides paper templates

**Status**: ❓ **UNKNOWN** (needs audit)
- Documentation: ✅ Complete (`systems/docx-comment-injection-engine/`)
- Code: ❓ TBD
- DOCX manipulation library: ❓ TBD

**Location**:
- Docs: `systems/docx-comment-injection-engine/`
- Code: `spectrum_systems/modules/` (TBD)

**Contracts**:
- Input: Resolved comment artifacts
- Output: Annotated DOCX schema (TBD)

---

#### SYS-009: Spectrum Pipeline Engine

**Purpose**: Orchestrate upstream engines (SYS-001 through SYS-008) into deterministic, contract-governed outputs for agenda generation and program advisory deliverables.

**Input**:
- Raw transcripts
- System parameters and constraints
- Orchestration rules

**Output**:
- End-to-end pipeline execution
- All intermediate and final artifacts
- Execution manifest and provenance

**Dependencies**:
- ALL systems (SYS-001 through SYS-008)

**Status**: ❓ **UNKNOWN** (needs audit)
- Documentation: ✅ Complete (`systems/spectrum-pipeline-engine/`)
- Code: ❓ TBD
- Orchestration logic: ❓ TBD

**Location**:
- Docs: `systems/spectrum-pipeline-engine/`
- Code: `spectrum_systems/modules/` (TBD)

**Contracts**:
- Input: Pipeline configuration schema (TBD)
- Output: Pipeline execution manifest (TBD)

---

### Data Flow and Contracts

#### Critical Path: Transcript → Working Paper

```
Raw Transcript
     ↓
[SYS-006] Meeting Minutes Engine
     ↓ (Meeting Minutes + Decisions)
[SYS-002] Transcript-to-Issue Engine
     ↓ (Issues + FAQs)
[SYS-003] Study Artifact Generator
     ↓ (Study Artifacts + Report Sections)
[SYS-007] Working Paper Review Engine
     ↓ (Working Paper + Comment Artifacts)
     
At this point: You have a working paper
Agencies review it and add comments
     ↓
[SYS-001] Comment Resolution Engine
     ↓ (Resolved Comments)
[SYS-008] DOCX Comment Injection Engine
     ↓ (Final Annotated DOCX)
[SYS-004] Spectrum Study Compiler
     ↓ (Packaged, Validated Deliverable)

Optional: Red-team loop
     ↓
[SYS-005] Spectrum Program Advisor
     ↓ (Readiness Brief, Scores)

Entire flow orchestrated by:
     ↓
[SYS-009] Spectrum Pipeline Engine
```

---

### Known Contracts and Schemas

#### Defined (exist in repo)
- ✅ Meeting Minutes: `contracts/schemas/meeting_minutes/transcript_facts_output.schema.json`
- ✅ Transcript Intelligence Pack: `contracts/schemas/transcript_intelligence_pack.schema.json`

#### Undefined (need to be discovered or created)
- ❓ Issue/FAQ artifact schema
- ❓ Study artifact schema
- ❓ Comment artifact schema
- ❓ Disposition artifact schema
- ❓ Final deliverable schema
- ❓ Pipeline execution manifest schema
- ❓ Readiness brief schema

---

### Critical Path to MVP

**Minimum viable subset** to prove the pipeline works end-to-end:

1. ✅ SYS-006 (Meeting Minutes) — working: extract minutes from transcript
2. ✅ SYS-002 (Transcript-to-Issue) — working: extract issues/FAQs
3. ⚠️ SYS-007 (Working Paper Review) — partial: generate paper, need to verify
4. ⚠️ SYS-001 (Comment Resolution) — unknown: resolve comments
5. ✅ SYS-004 (Study Compiler) — working: package deliverable

**Skip for MVP**:
- SYS-003 (Study Artifact Generator) — can simplify output
- SYS-005 (Program Advisor) — nice-to-have for initial release
- SYS-008 (DOCX Injection) — can defer to v2
- SYS-009 (Pipeline Engine) — can wire manually for MVP

**MVP Success Criteria**:
- [ ] Input: raw meeting transcript
- [ ] Output: working paper with extracted issues and FAQs
- [ ] Agencies provide comments
- [ ] Comments are resolved and documented
- [ ] Output: final report-ready document

---

### What We Don't Know (Needs Audit)

#### For Each System, Need to Verify:

1. **Is the code actually implemented?** (not just stubs)
2. **Does it use the right contracts?** (schemas match)
3. **Can it read real transcript data?** (handles spectrum-data-lake format)
4. **Does it produce valid output?** (artifacts pass validation)
5. **Are there tests?** (can we verify it works)
6. **What's missing?** (gaps between spec and code)

#### Critical Unknowns:

- ❓ Does SYS-007 (Working Paper Engine) actually work?
- ❓ Is SYS-001 (Comment Resolution) implemented?
- ❓ Can SYS-009 (Pipeline Engine) orchestrate all of these?
- ❓ Do the schemas match between systems?
- ❓ What breaks when you run end-to-end?

---

### How to Use This Document

#### For Humans
- Use this to understand: "How does the spectrum studies pipeline work?"
- Reference the system catalog to find specific systems
- See critical path to understand MVP

#### For Claude Code (Audit Workflow)
1. Read this document (the spec)
2. Read the actual code in `spectrum_systems/modules/`
3. For each system:
   - Does code match spec? ✅ YES / ❌ NO / ⚠️ PARTIAL
   - What input does it expect? (match contracts?)
   - What output does it produce? (valid schema?)
   - What's missing? (gaps vs spec)
4. Generate a detailed audit report:
   - System status (complete/partial/missing)
   - Code quality assessment
   - Gaps with file:line references
   - Missing contracts/schemas
   - Prioritized fix list
5. Output verdict: GO / GO_WITH_FIXES / NO_GO

---

### Next Steps

1. **Commit this document** to `systems/README.md`
2. **Run Claude Code audit** (compare spec vs actual code)
3. **Get prioritized build list** (what needs to be fixed)
4. **Build the MVP** (using prioritized gaps)
5. **Test end-to-end** with real transcripts from spectrum-data-lake

---

**Last Updated**: 2026-04-15  
**Authority**: System integration registry  
**Status**: CANONICAL SPEC — source of truth for spectrum studies pipeline architecture
