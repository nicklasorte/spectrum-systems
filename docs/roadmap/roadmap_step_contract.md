This file is subordinate to active editorial authority `docs/roadmaps/system_roadmap.md` and is enforced by machine execution surface `docs/roadmap/system_roadmap.md` during compatibility transition

# Roadmap Step Contract (PQX Execution Standard)

A roadmap step is considered **PQX-executable** only if ALL required fields are present.

This contract defines the minimum information required for a step to be executed without inference.

---

## REQUIRED FIELDS

| Field | Requirement |
|------|------------|
| Step ID | Unique, stable identifier |
| Title | Clear, descriptive name |
| Intent | Why this step exists |
| Scope In | What is included |
| Scope Out | What is excluded |
| Repo Seams | Exact files/modules to inspect first |
| Implementation Mode | MODIFY EXISTING / ADD NEW |
| Contracts | Exact schema files |
| Inputs | Required upstream artifacts |
| Outputs | Required produced artifacts |
| Control Loop Role | Observe / Interpret / Decide / Enforce / Learn |
| Dependencies | Direct prerequisites only |
| Build Tasks | Concrete implementation actions |
| Validation | Exact tests or commands |
| Failure Modes | What must fail closed |
| DoD | Binary definition of done |
| Non-Goals | Explicit exclusions |
| Slice Spec | Path to slice execution doc |

---

## HARD RULES

- No field may be vague
- No field may require interpretation
- No field may be empty
- Repo seams must point to real files
- Contracts must point to real schemas
- Validation must be runnable
- DoD must be binary (pass/fail)

---

## FAILURE CONDITION

If ANY field is missing or ambiguous:

→ The step is NOT executable  
→ PQX must NOT run it  

---

## PRINCIPLE

The roadmap is not a plan.

The roadmap is a **machine-readable execution contract**.

## Authority anchoring (B2 bridge)

- Active authority declaration: `docs/roadmaps/system_roadmap.md`.
- Machine execution surface during compatibility transition: `docs/roadmap/system_roadmap.md`.
- PQX must resolve these via `docs/roadmaps/roadmap_authority.md` and fail closed on ambiguity/mismatch before evaluating step rows.
