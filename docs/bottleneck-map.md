# Bottleneck Map: Spectrum / Engineering / Policy System

## A. Data Bottlenecks
1. Fragmented source systems
   - Allocation data, licensing data, federal assignment data, satellite data, terrain, clutter, population, and coordination records live in separate systems with different schemas.
2. No common spatial-temporal data model
   - Frequency, geography, time, service, emission characteristics, and incumbency are not represented in one unified queryable structure.
3. Manual data cleaning and reconciliation
   - Engineers spend too much time cleaning, reformatting, aligning, and checking data before analysis even begins.
4. Weak provenance / traceability
   - It is often hard to answer: where did this number come from, what source version was used, and what assumptions transformed it?
5. Poor access to historical studies and prior decisions
   - Past work exists, but retrieval is inconsistent and often depends on who remembers what.
6. Non-machine-readable source material
   - Key engineering and policy inputs live in PDFs, spreadsheets, memos, and narrative documents rather than structured data.
7. Inconsistent naming / taxonomy
   - Bands, systems, services, site names, and study assumptions are labeled inconsistently across documents and teams.
8. Lack of live or current operational context
   - For some systems, the best available data is stale, incomplete, or not updated in a way that supports current engineering analysis.

## B. Analytical Bottlenecks
9. Handcrafted study pipelines
   - Each new study is built like a custom snowflake instead of a reusable workflow.
10. Too much expert effort spent on repeat analysis
   - The same categories of calculations, table-building, assumption-checking, and write-up happen again and again.
11. Assumption management is weak
   - Critical assumptions are often buried in code, spreadsheets, email threads, or meeting memory rather than surfaced and versioned.
12. Sensitivity analysis is slow
   - It is too hard to test how outputs change when assumptions, deployment models, or thresholds change.
13. Reproducibility gaps
   - Another engineer may struggle to fully reproduce a result without the original analyst walking them through it.
14. Simulation-to-report gap
   - There is a large manual translation step between technical output and report-ready language.
15. Poor standardization of methods
   - Similar studies may use slightly different methods, criteria, or output formats, making comparisons harder.
16. High cycle time for engineering iteration
   - Questions that should take hours can take days or weeks because the workflow is not modularized.
17. No "default model stack"
   - Teams may debate which method to use each time instead of starting from an agreed baseline model stack.
18. Edge-case handling is fragile
   - Unusual systems, exemptions, footnotes, legacy constraints, or mixed service conditions break otherwise clean workflows.

## C. Knowledge Bottlenecks
19. Tribal knowledge concentration
   - Important engineering and policy knowledge lives in people's heads.
20. Retirement / turnover risk
   - When senior people leave, the reasoning behind past choices leaves with them.
21. Weak precedent retrieval
   - Similar prior cases exist, but there is no good way to quickly find analogous cases and extract the relevant logic.
22. Hidden decision heuristics
   - The real rules of thumb used by experienced staff are rarely documented cleanly.
23. Low transferability of expertise
   - New staff take too long to become effective because the system depends on informal apprenticeship.
24. Institutional memory is document-heavy, not queryable
   - The archive exists, but it does not behave like a memory engine.

## D. Process Bottlenecks
25. Coordination overhead
   - Multi-agency work creates delays from review cycles, comments, scheduling, consensus-building, and differing priorities.
26. Comment resolution is labor-intensive
   - Agency comments come in spreadsheets and narrative form, and converting them into coherent disposition text is slow.
27. No standard intake-to-output workflow
   - Inputs arrive in many forms, but there is no unified pipeline from question -> analysis -> output -> disposition.
28. Meeting output evaporates
   - A lot of insight is generated in calls and TIGs, but extraction into durable, reusable artifacts is weak.
29. Too many manual handoffs
   - Data moves from one person to another, then to slides, then to memos, then to reports, with loss at each step.
30. Decision latency
   - The system is slow to answer because each answer requires fresh assembly of context.
31. Weak issue tracking for engineering-policy questions
   - Open questions, partial answers, and dependencies are not always tracked in a durable way.
32. Version confusion
   - People work off slightly different versions of tables, assumptions, and draft language.
33. Poor closure discipline
   - Questions can linger without an explicit disposition: answered, partial, deferred, or rejected.

## E. Document / Communication Bottlenecks
34. Narrative burying logic
   - Important logic is often buried inside long prose instead of surfaced as explicit claims, assumptions, methods, and outputs.
35. Report writing begins too late
   - Teams often treat writing as the final step rather than building report-ready artifacts throughout the study.
36. Weak translation across audiences
   - Engineering results are not always translated cleanly for lawyers, policymakers, executives, or external stakeholders.
37. Repetitive drafting from blank pages
   - Similar sections get rewritten over and over instead of generated from structured components.
38. Tables and figures are not "born structured"
   - Outputs are often created for one-off use, not downstream reuse in reports, FAQs, or decision memos.
39. Unclear linkage between comments and report text
   - It can be hard to map a comment to the exact section, line, or replacement text that resolves it.

## F. Governance / Decision Bottlenecks
40. Ambiguous decision criteria
   - Sometimes it is not obvious what standard is actually driving the decision: legal, engineering, policy, political, timing, or optics.
41. Mixed authority environment
   - NTIA, FCC, agencies, and other actors each hold part of the decision landscape.
42. Lack of explicit risk frameworks
   - Tradeoffs are discussed, but not always within a structured risk language.
43. Incentive mismatch
   - Different actors optimize for different things: speed, protection, precedent, optionality, political defensibility, or turf.
44. Preference for bespoke judgment over structured process
   - Institutions often reward expert discretion even when structured systems would improve speed and consistency.
45. Fear of transparency
   - More reproducible analysis can expose assumptions, disagreement, and uncertainty, which some actors dislike.
46. Hard to separate technical disagreement from institutional posture
   - What looks like engineering debate may partly be a negotiation tactic or risk posture.

## G. Human / Organizational Bottlenecks
47. Expert attention is scarce
   - The most valuable people are spending time on formatting, lookup, coordination, and repetitive synthesis.
48. Cognitive overload
   - Individuals are forced to hold too many moving pieces in working memory.
49. Training burden on managers / senior engineers
   - Senior staff become human APIs for every recurring question.
50. Cultural resistance to new systems
   - Even good tools can fail if they threaten identity, autonomy, or established ways of working.
51. Tool fragmentation
   - Work is spread across email, Excel, PDFs, code, slides, shared drives, and meetings with weak integration.
52. Underpowered staffing relative to complexity
   - The system depends on heroic effort because there are not enough people for the volume and difficulty of work.
53. Weak onboarding architecture
   - New engineers are not dropped into a system that teaches them the workflow; they are dropped into a maze.

## H. AI-Specific Bottlenecks
54. AI use is mostly ad hoc
   - People use chat interfaces for isolated tasks instead of building durable automated workflows.
55. No trusted structured prompts / evaluators / pipelines
   - AI outputs vary because the organization lacks standardized schemas, guardrails, and QA loops.
56. Weak human-in-the-loop design
   - There is no clear definition of what AI should automate, what humans should review, and where approval gates belong.
57. Data security / access constraints
   - Valuable AI workflows are limited by concerns about what data can be used where.
58. Lack of evaluation harnesses
   - Teams do not have systematic ways to test whether an AI workflow is actually accurate and useful.
59. No institutional AI memory
   - AI is often used session by session, not as a persistent knowledge and workflow layer.
60. Missing automation mindset
   - Many people stop at "AI can help me write this," instead of asking "which recurring process should become a system?"
