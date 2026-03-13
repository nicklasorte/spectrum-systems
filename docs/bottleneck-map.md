# Bottleneck Map: Spectrum / Engineering / Policy System

## Top Strategic Bottlenecks

### BN-001 Comment Resolution Workflow
- **Description**: Turning multi-agency comment spreadsheets and narrative feedback into structured dispositions with traceability back to source sections.
- **Why it slows decision-making**: Decision memos wait on manual reconciliation of duplicate threads, unclear owners, and missing links to report text, delaying approvals.
- **Why it consumes expert time**: Senior engineers re-read source sections, restate requirements, and craft disposition language by hand for each comment cycle.
- **Why it is suitable for automation**: Comment ingestion, clustering, mapping to sections, and draft disposition generation can be schema-driven with human review checkpoints.
- **What system would solve it**: Comment Resolution Engine that enforces `comment-schema`, aligns comments to report sections, drafts dispositions, and routes for review.

### BN-002 Transcript to Issue Extraction
- **Description**: Converting raw meeting transcripts into structured, prioritized issues with categories, owners, and dependencies.
- **Why it slows decision-making**: Action items linger because open questions and blockers are not captured into the backlog immediately after discussions.
- **Why it consumes expert time**: Experts skim transcripts, manually extract issues, and coordinate ownership instead of advancing analyses.
- **Why it is suitable for automation**: Modern extraction models can map utterances to `issue-schema`, enrich with context, and surface uncertainties for review.
- **What system would solve it**: Transcript-to-Issue Engine that applies `issue-schema`, tags categories, links to prior artifacts, and posts to the backlog.

### BN-003 Simulation Output to Report Artifact Generation
- **Description**: Translating simulation outputs into tables, figures, and narrative that align with report sections and provenance requirements.
- **Why it slows decision-making**: Reports stall while engineers translate raw outputs into stakeholder-ready language and visuals.
- **Why it consumes expert time**: Experts format tables, craft narrative, and check consistency instead of iterating on models.
- **Why it is suitable for automation**: Output parsing, templated rendering, and schema validation can reliably produce artifacts with embedded provenance for review.
- **What system would solve it**: Study Artifact Generator that converts simulation outputs using `study-output-schema`, applies templates, and prepares report-ready sections with traceability.

| Bottleneck | Category | Description | Impact | Frequency | Expert Time Cost | Automation Potential | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Fragmented source systems | Data | Allocation, licensing, assignment, satellite, terrain, clutter, population, and coordination records live in separate systems with different schemas. | High | Frequent | High | Medium | High |
| No common spatial-temporal data model | Data | Frequency, geography, time, service, emission characteristics, and incumbency are not represented in one unified queryable structure. | High | Frequent | High | Medium | High |
| Manual data cleaning and reconciliation | Data | Engineers spend significant time cleaning, reformatting, aligning, and checking data before analysis begins. | High | Frequent | High | High | High |
| Weak provenance / traceability | Data | Hard to answer where numbers came from, which source version was used, and what assumptions transformed it. | High | Frequent | Medium | Medium | High |
| Poor access to historical studies and prior decisions | Data | Retrieval is inconsistent and depends on institutional memory rather than structured access. | Medium | Occasional | Medium | Medium | Medium |
| Non-machine-readable source material | Data | Key inputs live in PDFs, spreadsheets, memos, and narrative documents instead of structured data. | High | Frequent | High | High | High |
| Inconsistent naming / taxonomy | Data | Bands, systems, services, site names, and study assumptions are labeled inconsistently across teams. | Medium | Frequent | Medium | Medium | Medium |
| Lack of live or current operational context | Data | Available data is stale, incomplete, or not updated to support current engineering analysis. | High | Occasional | Medium | Medium | High |
| Handcrafted study pipelines | Analytical | Each study is a custom build instead of a reusable workflow. | High | Frequent | High | High | High |
| Too much expert effort spent on repeat analysis | Analytical | Repetitive calculations, table-building, assumption-checking, and write-up consume expert cycles. | High | Frequent | High | High | High |
| Assumption management is weak | Analytical | Critical assumptions are buried in code, spreadsheets, or memory instead of surfaced and versioned. | High | Frequent | Medium | Medium | High |
| Sensitivity analysis is slow | Analytical | Difficult to test how outputs change when assumptions or models vary. | Medium | Occasional | Medium | Medium | Medium |
| Reproducibility gaps | Analytical | Another engineer may struggle to fully reproduce results without guidance. | High | Occasional | Medium | Medium | High |
| Simulation-to-report gap | Analytical | Large manual translation step between technical outputs and report-ready language. | High | Frequent | High | High | High |
| Poor standardization of methods | Analytical | Similar studies use different methods, criteria, or formats, hindering comparison. | Medium | Occasional | Medium | Medium | Medium |
| High cycle time for engineering iteration | Analytical | Questions that should take hours take days or weeks because workflows are not modular. | High | Frequent | High | High | High |
| No default model stack | Analytical | Teams debate methods each time instead of starting from a baseline model stack. | Medium | Occasional | Medium | Medium | Medium |
| Edge-case handling is fragile | Analytical | Unusual systems, exemptions, or mixed service conditions break otherwise clean workflows. | Medium | Occasional | Medium | Medium | Medium |
| Tribal knowledge concentration | Knowledge | Critical engineering and policy knowledge lives in people's heads. | High | Frequent | High | Medium | High |
| Retirement / turnover risk | Knowledge | Reasoning behind past choices leaves with departing staff. | High | Occasional | Medium | Medium | High |
| Weak precedent retrieval | Knowledge | Similar prior cases exist but are hard to find and reuse. | High | Occasional | Medium | Medium | High |
| Hidden decision heuristics | Knowledge | Rules of thumb used by experienced staff are undocumented. | Medium | Occasional | Medium | Low | Medium |
| Low transferability of expertise | Knowledge | New staff take too long to become effective due to informal apprenticeship. | High | Occasional | High | Medium | High |
| Institutional memory is document-heavy, not queryable | Knowledge | Archives exist but do not behave like a searchable memory engine. | High | Frequent | Medium | Medium | High |
| Coordination overhead | Process | Multi-agency work faces delays from review cycles, comments, scheduling, and differing priorities. | High | Frequent | High | Medium | High |
| Comment resolution is labor-intensive | Process | Agency comments need conversion into coherent disposition text. | High | Frequent | High | High | High |
| No standard intake-to-output workflow | Process | Inputs arrive in many forms without a unified pipeline from question to disposition. | High | Frequent | High | Medium | High |
| Meeting output evaporates | Process | Insights from calls and TIGs are not captured into durable artifacts. | Medium | Frequent | Medium | Medium | High |
| Too many manual handoffs | Process | Data passes person-to-person with losses at each step. | Medium | Frequent | Medium | Medium | Medium |
| Decision latency | Process | Answers require fresh assembly of context, slowing the system. | High | Occasional | Medium | Medium | High |
| Weak issue tracking for engineering-policy questions | Process | Open questions and dependencies are not tracked durably. | High | Frequent | Medium | Medium | High |
| Version confusion | Process | Teams work off different versions of tables, assumptions, and drafts. | Medium | Frequent | Medium | Medium | Medium |
| Poor closure discipline | Process | Questions linger without explicit disposition. | Medium | Occasional | Medium | Medium | Medium |
| Narrative burying logic | Document / Communication | Logic is buried inside prose instead of explicit claims, assumptions, methods, and outputs. | Medium | Frequent | Medium | Medium | Medium |
| Report writing begins too late | Document / Communication | Writing is treated as the final step instead of continuous artifact production. | High | Frequent | High | Medium | High |
| Weak translation across audiences | Document / Communication | Engineering results are not cleanly translated for varied stakeholders. | Medium | Occasional | Medium | Medium | Medium |
| Repetitive drafting from blank pages | Document / Communication | Similar sections get rewritten instead of assembled from structured components. | Medium | Frequent | Medium | High | Medium |
| Tables and figures are not born structured | Document / Communication | Outputs are created for one-off use, not downstream reuse. | Medium | Frequent | Medium | High | Medium |
| Unclear linkage between comments and report text | Document / Communication | Hard to map a comment to exact sections, lines, or replacement text. | Medium | Occasional | Medium | Medium | Medium |
| Ambiguous decision criteria | Governance / Decision | Standards driving decisions are unclear across legal, engineering, policy, and political dimensions. | High | Occasional | Medium | Low | High |
| Mixed authority environment | Governance / Decision | Multiple actors each hold part of the decision landscape. | High | Frequent | Medium | Low | High |
| Lack of explicit risk frameworks | Governance / Decision | Tradeoffs are discussed without a structured risk language. | High | Occasional | Medium | Medium | High |
| Incentive mismatch | Governance / Decision | Different actors optimize for divergent objectives. | Medium | Occasional | Medium | Low | Medium |
| Preference for bespoke judgment over structured process | Governance / Decision | Expert discretion is rewarded over standardized workflows. | Medium | Frequent | Medium | Low | Medium |
| Fear of transparency | Governance / Decision | Reproducible analysis may expose assumptions and disagreements. | Medium | Occasional | Medium | Low | Medium |
| Hard to separate technical disagreement from institutional posture | Governance / Decision | Engineering debate may reflect negotiation tactics or posture. | Medium | Occasional | Medium | Low | Medium |
| Expert attention is scarce | Human / Organizational | High-value people spend time on formatting, lookup, coordination, and repetitive synthesis. | High | Frequent | High | Medium | High |
| Cognitive overload | Human / Organizational | Individuals hold too many moving pieces in working memory. | Medium | Frequent | Medium | Medium | Medium |
| Training burden on managers / senior engineers | Human / Organizational | Senior staff act as human APIs for recurring questions. | Medium | Frequent | High | Medium | Medium |
| Cultural resistance to new systems | Human / Organizational | New tools can threaten identity, autonomy, or established ways. | Medium | Occasional | Medium | Low | Medium |
| Tool fragmentation | Human / Organizational | Work spreads across many tools with weak integration. | Medium | Frequent | Medium | Medium | Medium |
| Underpowered staffing relative to complexity | Human / Organizational | System depends on heroic effort due to insufficient staffing. | High | Occasional | High | Medium | High |
| Weak onboarding architecture | Human / Organizational | New engineers lack a system that teaches the workflow. | Medium | Occasional | Medium | Medium | Medium |
| AI use is mostly ad hoc | AI-Specific | AI is used for isolated tasks instead of durable workflows. | High | Frequent | Medium | High | High |
| No trusted structured prompts / evaluators / pipelines | AI-Specific | Lack of standardized schemas, guardrails, and QA loops produces variable outputs. | High | Frequent | Medium | High | High |
| Weak human-in-the-loop design | AI-Specific | No clear definition of automation vs. review and approval gates. | High | Occasional | Medium | Medium | High |
| Data security / access constraints | AI-Specific | Valuable AI workflows limited by data usage concerns. | High | Occasional | Medium | Low | Medium |
| Lack of evaluation harnesses | AI-Specific | No systematic ways to test AI workflow accuracy and usefulness. | High | Frequent | Medium | High | High |
| No institutional AI memory | AI-Specific | AI usage is session-based instead of persistent knowledge and workflow layer. | High | Frequent | Medium | High | High |
| Missing automation mindset | AI-Specific | Teams stop at ad hoc assistance rather than system-level automation. | High | Frequent | Medium | High | High |
