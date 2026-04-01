# Spectrum Systems — Strategy-Guided Roadmap Prompt

You are acting as a staff-level architect performing a source-grounded strategy compliance audit and next-step roadmap generation for Spectrum Systems.

Your task is to inspect the current repository state and produce the next 20–30 dependency-valid roadmap steps.

You must treat the following as authoritative inputs, in this order:
1. the Strategy Control Document
2. docs/architecture/foundation_pqx_eval_control.md
3. docs/architecture/ai_operating_substrate_and_artifact_intelligence.md
4. the current repository
5. the current roadmap
6. source design documents and architecture artifacts

NON-NEGOTIABLE REQUIREMENTS

1. STRATEGY ENFORCEMENT
Every roadmap step must align to the Strategy Control Document.
You must explicitly check every proposed step against:
- system invariants
- system boundaries
- stable vs replaceable layer rules
- control loop rules
- roadmap generation rules
- drift detection rules

2. FOUNDATION BEFORE EXPANSION
Do not prioritize new capability if earlier trust, replay, eval, observability, control, certification, routing, context, or substrate slices are incomplete, partial, bypassable, or weak.
When earlier slices are weak, prioritize hardening first.

3. NO AGENT-FIRST DRIFT
Do not propose agent-first, prompt-first, or model-coupled roadmap steps unless they are bounded by contracts, evals, traces, policy, and control integration in the same step group.

4. EVERY STEP MUST JUSTIFY ITSELF
For each roadmap step, state:
- what it does
- why it matters
- which strategy invariants it strengthens
- which trust, measurability, safety, replayability, or control property it improves

5. HARD GATES
Prefer steps that improve one or more of the following:
- schema discipline
- replay determinism
- eval coverage
- observability completeness
- policy authority
- certification and promotion rigor
- judgment capture and reuse
- AI substrate governance
- artifact intelligence readiness

6. DRIFT HANDLING
If the repo shows architecture drift, your roadmap must explicitly pivot toward stabilization before expansion.
Examples of drift include:
- missing evals
- schema bypasses
- weak traceability
- control bypasses
- ungoverned outputs
- weak replayability
- capability added without promotion discipline
- substrate expansion without new measurement or governance surfaces

7. REPO INTERPRETATION RULE
Treat the repository as an implemented but incomplete governed system.
Prefer hardening, connecting, validating, and governing existing seams rather than redesigning from scratch.

8. GOLDEN PATH BUILDABILITY CHECK
Before proposing roadmap expansion, you must explicitly assess golden path buildability.

You must include a section titled exactly:
Golden Path Buildability Status

In that section, you must evaluate whether the current repo can execute the golden path end to end.
At minimum, assess whether the repo currently supports:
- artifact creation
- schema validation
- required eval generation
- eval summary rollup
- deterministic control decision
- enforcement action execution
- replay support
- trace completeness
- promotion or certification checkpoint

You must then output exactly one of:
- BUILDABLE
- PARTIALLY BUILDABLE
- NOT BUILDABLE

You must also list:
- seams already implemented
- seams missing
- seams weak or bypassable
- the next hard gate required before further expansion

Treat “documented but not implemented” as NOT BUILDABLE.
Treat missing required evals, weak replay, weak traceability, missing control integration, or missing promotion or certification rigor as NOT BUILDABLE or PARTIALLY BUILDABLE.

9. FOUNDATION EXPANSION BLOCK
You must explicitly determine whether expansion is allowed.

You must include a section titled exactly:
Expansion Decision

In that section, you must output exactly one of:
- EXPANSION ALLOWED
- EXPANSION LIMITED
- EXPANSION BLOCKED

You must mark expansion as EXPANSION BLOCKED if any of the following are true:
- required contracts are missing
- required evals are missing
- replay is missing or weak
- traceability is missing or weak
- control integration is missing or bypassable
- certification or promotion hard gates are missing
- the golden path is PARTIALLY BUILDABLE
- the golden path is NOT BUILDABLE
- a foundation slice is weak, partial, incomplete, or bypassable

If expansion is EXPANSION BLOCKED, the roadmap must fail closed against expansion and pivot to stabilization and hardening only.
If expansion is EXPANSION LIMITED, only tightly bounded substrate-hardening work may proceed.
You must not propose broader capability expansion while foundation gaps remain.

10. OUTPUT CLASSIFICATION
Each roadmap step must classify itself as one of:
- foundation hardening
- substrate build
- substrate hardening
- artifact intelligence build
- depends on missing foundation
- blocked until hard gate passes

OUTPUT FORMAT

Return:
1. a section titled exactly:
Current Strategy Risks

2. a section titled exactly:
Golden Path Buildability Status

3. a section titled exactly:
Expansion Decision

4. a single markdown table with these columns:
- ID
- Prompt
- Status
- What It Does
- Why It Matters
- Strategy Alignment
- Primary Trust Gain
- Step Class

5. a section titled exactly:
Recommended Next Hard Gate

ADDITIONAL OUTPUT REQUIREMENTS
- Be explicit when later steps depend on earlier stabilization.
- If Expansion Decision is EXPANSION BLOCKED, the first roadmap tranche must be hardening-only.
- Name and number prompts explicitly using this format:
  - Prompt 1 — <title>
  - Prompt 2 — <title>
  - Prompt 3 — <title>

QUALITY BAR
The roadmap must be:
- dependency-valid
- governance-complete
- failure-mode-aware
- repo-native
- aligned to the Strategy Control Document
- foundation-aware
- golden-path-aware
- explicit about whether expansion is blocked
- realistic for incremental implementation

A roadmap that does not explicitly report Golden Path Buildability Status and Expansion Decision is invalid.

Do not produce vague ideas.
Do not hand-wave partial foundations as complete.
Produce buildable next steps.
