# System Philosophy

Spectrum Systems treats every automation capability as an accountable, reviewable system rather than a loose collection of prompts. The philosophy below keeps the architecture maintainable and deterministic.

## Core Beliefs
- **Design-first**: Define the problem, data model, and evaluation gates before implementation.
- **Schema-led**: Schemas are the source of truth for inputs, intermediates, and outputs.
- **Deterministic by default**: Prompts, rules, and workflows should produce repeatable outputs given the same inputs.
- **Human-in-the-loop**: AI augments experts; review checkpoints are mandatory for material artifacts.
- **Traceable lineage**: Provenance and reproducibility metadata must accompany every artifact that can affect a decision.
- **Composable systems**: Each system exposes a clear interface and contracts so other systems can safely depend on it.

## Practical Implications
- New systems start as documents: problem statement, interface, evaluation plan, and failure modes.
- Interfaces specify required schemas, prompts, workflows, and evaluation harnesses before code exists.
- Every artifact chain step declares its upstream dependencies and downstream consumers.
- Model prompts and rules are versioned; changes require re-running evaluation harnesses.
- Validation failures are explicit and blocking; silent degradation is not acceptable.

## Scope Boundaries
- This repository holds architecture, standards, schemas, prompts, and evaluation scaffolds.
- Implementation code lives in separate repositories that import these standards.
- Automation code must not be added here until workflows, schemas, and evaluations are stable.

## How to Use This Philosophy
1. Start with `docs/system-map.md` to see the current systems and their dependencies.
2. For any system, read `systems/<system>/overview.md` then `interface.md` to understand its contract.
3. Follow the evaluation plan before trusting outputs; if missing, add it before writing code.
4. Keep terminology consistent with `docs/terminology.md` and schemas consistent with `schemas/README.md`.
