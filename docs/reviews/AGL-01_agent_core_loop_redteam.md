# AGL-01 Agent Core Loop Red-Team Review

## must_fix
- None. All listed attacks are blocked by schema and builder fail-closed behavior.

## should_fix
- Expand source-artifact parsers for more upstream artifact families to improve confidence from unknown -> present.

## observation
- Free-text PR content is not used as evidence; only artifact refs are counted.
- MET authority is constrained to `observation_only`.
- Unknown never counts as present.
