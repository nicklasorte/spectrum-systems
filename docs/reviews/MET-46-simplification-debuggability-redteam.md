# MET-46 Simplification and Debuggability Red-Team

## Prompt type
REVIEW

## Findings

### must_fix
1. **Fold-ready observation must be blocked unless all five coverage booleans are true.**
2. **Operator drill must include six fixed questions per drill item.**

### should_fix
1. Dashboard diagnostics should keep compact top-5 display limits.
2. Debug panel should surface source artifacts for new drill and owner-read sections.

### observation
1. No artifact removal is performed in this PR; fold candidates are observations only.
2. New compact sections are additive and do not introduce giant tables.
