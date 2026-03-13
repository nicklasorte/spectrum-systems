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

Follow `docs/system-interface-spec.md` and `docs/system-lifecycle.md` when adding or updating a system.
