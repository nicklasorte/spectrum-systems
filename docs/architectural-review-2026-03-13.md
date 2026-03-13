# Architectural Review: Spectrum Systems

**Date:** 2026-03-13
**Reviewer:** Claude (Reasoning Agent)
**Scope:** Full repository — conceptual clarity, structural coherence, terminology consistency, missing connections, and design completeness

---

## Onboarding Benchmark

This review evaluates the repository against a concrete standard: can a new engineer develop a coherent mental model of the system within 20 minutes? The short answer is: the architecture is sound, but navigation barriers prevent that goal from being met today. The fixes are low-cost and do not require rethinking any design decision.

---

## 1. Major Clarity Issues

**CI-1: "System" is overloaded without a type hierarchy.**
"System" is used to mean an automation tool (Comment Resolution Engine), the multi-system architecture overall, and occasionally an existing source system. `systems-registry.md` catalogs automation tools but never distinguishes these three meanings. Recommend defining: *automation system* (what we build), *source system* (existing tools), *data system* (the data lake and its components).

**CI-2: "Artifact" is undefined relative to "document", "record", and "output".**
`artifact-chain.md` defines a canonical workflow but "artifact" is used throughout the repo to mean: a schema-defined record, a report section, a file produced by a pipeline, and a design document in this repo. There is no authoritative definition distinguishing artifact from record, output, or deliverable. This needs a precise GLOSSARY entry.

**CI-3: The data lake has no defined boundary.**
`data-lake-strategy.md` defines 18 data classes across 4 tiers but never states what the data lake *is* in infrastructure terms: a structured file store, a database, a cloud bucket, or a catalog. New engineers cannot connect schema definitions to any concrete storage reality. The strategy needs a one-paragraph infrastructure framing, even if approximate.

**CI-4: Provenance standard scope is ambiguous at ingestion.**
`data-provenance-standard.md` is thorough (33 fields, 5 enumerations). Decision 3 says provenance applies to "all structured data." However, system designs only explicitly enforce provenance at output, not at ingestion of raw inputs. The standard should state clearly: does provenance apply to (a) every record produced by an automation system, (b) only human-reviewed records, or (c) all structured data including raw inputs?

**CI-5: Bottleneck map is not linked to systems registry in-document.**
`bottleneck-map.md` identifies 86 bottlenecks but does not link individual bottlenecks to the systems that address them. `systems-registry.md` does not link systems back to the bottlenecks they resolve. The connection exists implicitly in other documents but not in the two primary documents that should be paired.

**CI-6: "Workflow" means two different things.**
In `workflows/`, a workflow is a system processing pipeline (ingest → normalize → validate). In `docs/`, "workflow" refers to the human engineering process being improved. Both meanings appear in the same sentences without distinction. Recommend: *processing pipeline* for system internals, *workflow* reserved for the human engineering activity.

---

## 2. Structural Improvements

**SI-1: Canonicalize system design documents.**
System docs now live under `systems/<system>/` with a single set of `overview`, `interface`, `design`, `evaluation`, and `prompts` files. Keep these as the canonical locations and avoid parallel specs elsewhere.

**SI-2: Clarify the relationship between root-level schemas and data-lake schemas.**
`schemas/` contains 6 minimal schemas (10–13 fields). `schemas/data-lake/` contains 5 far more complete schemas with full provenance coverage and worked examples. A new engineer reads the root schemas first, forms expectations, then discovers the data-lake schemas are a completely different level of maturity. Either consolidate into one location or add a `schemas/README.md` that explicitly explains: which are canonical, which are derivative, and the intended evolution path.

**SI-3: Separate `issues/` from `open-research-questions.md`.**
Both track open questions and backlog items without a defined relationship. Recommend a clean split: `issues/` = implementation backlog (Codex/Copilot tasks); `docs/open-research-questions.md` = design-phase unknowns requiring reasoning (Claude tasks). Add a one-line note at the top of each explaining the distinction.

**SI-4: Absorb `REPO_MAP.md` into `README.md`.**
`README.md` and `REPO_MAP.md` both provide directory overviews and navigation links. The duplication creates two sources of truth for repository structure. Absorb `REPO_MAP.md` into `README.md` as a dedicated navigation section and remove the standalone file.

**SI-5: Connect evaluation harnesses to system specs.**
Evaluation criteria appear in three places: inside workflow files, inside system specs, and in `eval/*/README.md`. There is no single authoritative location. Each system spec should include a direct link to its eval harness, and each eval harness should reference back to the acceptance criteria in the spec.

**SI-6: Add a `prompts/README.md` index.**
`prompts/` contains prompt files with no governing index. `prompt-standard.md` defines structure but does not register existing prompts. Add a `prompts/README.md` that catalogs each prompt, the system it belongs to, its version, and a link to the system spec.

---

## 3. Terminology Fixes

The following inconsistencies appear across documents and should be resolved in `GLOSSARY.md`:

| Term Pair | Current State | Recommended Distinction |
|---|---|---|
| **artifact vs record vs output** | Used interchangeably | *artifact* = human-reviewed structured output; *record* = schema-compliant data entry; *output* = any system-produced result |
| **system vs workflow** | Conflated in several docs | *system* = automation tool; *workflow* = processing pipeline within a system; *process* = human engineering activity being automated |
| **data class vs schema vs dataset** | Used interchangeably in data lake docs | *data class* = logical category (Tier 1–4); *schema* = field-level definition; *dataset* = populated collection of records |
| **disposition vs resolution** | Swapped in comment-resolution docs | *resolution* = the process; *disposition* = the decision recorded against a specific comment |
| **study vs analysis vs report** | Used interchangeably in study artifact docs | *study* = the overall engagement; *analysis* = a discrete analytical component; *report* = the deliverable |
| **assumption vs constraint vs parameter** | Used interchangeably in system designs | *assumption* = unverified input believed true; *constraint* = bound on the solution; *parameter* = configurable value |

`GLOSSARY.md` defines concepts at a category level but does not yet distinguish related terms from each other at the precision needed for schema and system design work.

---

## 4. Missing Architectural Components

**MAC-1: No structured input/output specification table for any system.**
System designs describe inputs and outputs in prose. There is no structured table specifying: field name, data type, required/optional, source schema, and example value. Without this, implementation engineers cannot write parsers or validators from the design alone.

**MAC-2: No system boundary diagram.**
`system-architecture.md` describes a 6-stage pipeline in text. No diagram (even ASCII) shows how systems connect, where data flows between them, or where the data lake sits relative to each system. The overall architecture is never made concrete for a new reader.

**MAC-3: No schema versioning strategy.**
Schemas will evolve once implementation begins. There is no strategy for: how schema versions are numbered, what constitutes a breaking vs. non-breaking change, how existing records are migrated when a schema changes, or who approves schema changes. This gap will cause instability immediately upon first implementation.

**MAC-4: No error taxonomy.**
All three workflow blueprints mention routing low-confidence outputs to human review but do not define categories of failure modes, how they are classified, or what the remediation path is for each. A taxonomy of failure modes (extraction failure, schema violation, confidence below threshold, ambiguous mapping) is required before evaluation harnesses or routing logic can be built.

**MAC-5: No interface specification between systems.**
The three Phase 1 systems produce outputs that feed downstream systems. There is no defined interface spec covering: file format, transfer mechanism, validation at handoff, and error handling when a downstream system rejects an upstream output.

**MAC-6: No data retention or deletion policy.**
The provenance standard mandates immutability (Rule 10: no deletion), but there is no policy governing retention duration, handling of superseded versions, storage of raw inputs alongside processed outputs, or authority to purge erroneous records.

**MAC-7: The precedent system has a schema but no design.**
`precedent-schema.json` exists (sparsely, 5 fields), and the systems registry lists an Institutional Knowledge Engine, but there is no system design for how precedents are created, linked, queried, or governed. Downstream systems that claim to use precedent-based reasoning have no concrete foundation to build on.

---

## 5. Suggested Repository Improvements

**SRI-1: Add a prescribed reading order to `README.md`.**
New engineers need a sequenced onboarding path, not a flat list of links. Include an explicit reading sequence (why → bottlenecks → systems → interfaces → schemas → prompts/eval):

```
1. docs/vision.md
2. docs/bottleneck-map.md
3. SYSTEMS.md and docs/system-map.md
4. docs/system-philosophy.md and docs/system-interface-spec.md
5. docs/system-lifecycle.md and docs/system-status-registry.md
6. docs/data-provenance-standard.md and docs/reproducibility-standard.md
7. schemas/ and prompts/ (aligned with system folders)
```

**SRI-2: Implement bidirectional bottleneck-to-system links.**
In `bottleneck-map.md`, tag each Tier 1/2 bottleneck with the system addressing it: `→ SYS-001`. In `systems-registry.md`, tag each system with the bottleneck(s) it resolves: `← BN-053`. This turns an implicit relationship into an explicit, navigable one.

**SRI-3: Make `GLOSSARY.md` a normative reference.**
`GLOSSARY.md` is not referenced from any system design, schema, or workflow document. Add a convention: whenever a technical term is first used in a document, link to its GLOSSARY entry. Expand the glossary to cover the term pairs in Section 3.

**SRI-4: Expand eval harnesses with concrete test cases.**
Each `eval/*/README.md` defines evaluation criteria but contains no test data. Minimum viable harness per system: 5 normal-case inputs with labeled expected outputs, 2 edge-case inputs, 1 malformed input, and a scoring rubric with pass/fail thresholds.

**SRI-5: Record a schema governance decision in `DECISIONS.md`.**
The four current decisions cover repository philosophy, separation of concerns, provenance, and structured outputs. Missing is a formal decision on schema versioning and change governance. This decision will be needed the first time a schema field is added or renamed.

**SRI-6: Add a cross-reference index.**
Add `docs/system-map.md` mapping each system to its design doc, workflow, schema(s), prompt(s), and eval harness. This removes the navigation burden from new engineers and makes the architecture legible as a connected whole.

**SRI-7: Subdivide `docs/` as Phase 2 and 3 designs are added.**
Currently `docs/` is a flat directory mixing architectural frameworks, system designs, standards, and analysis documents. The flat structure works at current scale but will become disorienting as designs are added. Consider subdirectories: `docs/architecture/`, `docs/systems/`, `docs/standards/`, `docs/analysis/`.

---

## Summary

The repository is architecturally sound and internally consistent. The design philosophy is well-executed and the core artifacts — bottleneck map, provenance standard, data lake strategy, and system designs — are mature and thorough.

The primary risk for a new engineer is **navigation**: the connections between documents are described in prose but not implemented as links, cross-references, or structured indices. A new engineer spending 20 minutes here will understand the intent but will not form a clear mental model of how bottlenecks map to systems, systems map to schemas, or schemas map to provenance requirements.

All seven structural improvements above are low-cost documentation changes. None require rethinking any existing design decision. They should be prioritized before Phase 2 system designs are added, while the repository is still small enough to restructure cheaply.
