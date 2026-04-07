# Next Recommended Slice

## BATCH-GOV-FIX-02 — Governed Prompt Surface Registry Integration

Integrate governed prompt docs (`docs/governance/prompt_includes/*`, `docs/governance/prompt_templates/*`, and prompt seam templates under `prompts/` + `templates/review/`) into a single repo-native governed prompt surface registry (`docs/governance/governed_prompt_surfaces.json`) and add a deterministic test to verify every registered surface includes required governance references.

### Outcome target
- Keeps fail-closed prompt governance enforceable as prompt surface count grows.
- Prevents future contract preflight drift by requiring explicit surface registration + test-backed coverage.
