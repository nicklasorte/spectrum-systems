# HS-08 Multi-Pass Artifact Generation

HS-08 replaces single-pass final artifact construction with a fixed deterministic sequence:

1. `pass_1` (`extract`) — initial draft extraction.
2. `pass_2` (`critique`) — bounded structured critique.
3. `pass_3` (`refine`) — deterministic correction from critique.
4. `final` (`final`) — final governed artifact output.

## Pass sequence and constraints

- Sequence is fixed and explicit (`pass_1` → `pass_2` → `pass_3` → `final`).
- No dynamic iteration, no retry loops, no adaptive branching.
- Runtime fails closed on any malformed pass output or linkage inconsistency.

## Pass semantics

### Extract (`pass_1`)
- Accepts the candidate draft artifact from bounded agent execution.
- Produces canonicalized JSON output for downstream passes.

### Critique (`pass_2`)
- Produces structured fields only:
  - `missing_elements`
  - `inconsistencies`
  - `weak_reasoning`
  - `summary`
- Identifies missing fields, type inconsistencies, and unsupported/weak claims.
- Bounded (no unstructured essay output).

### Refine (`pass_3`)
- Consumes extract + critique outputs.
- Applies deterministic corrections only:
  - fill missing fields with governed placeholder
  - normalize `_id` fields to string type
  - remove unsupported claims (empty evidence refs)
- Emits corrected artifact + explicit `refinement_actions` list.

### Final (`final`)
- Emits final artifact derived from refined artifact.
- Downstream schema validation remains required at agent execution boundary.

## Trace and contract linkage

- Canonical record: `multi_pass_generation_record`.
- Runtime trace (`agent_execution_trace`) links to:
  - `multi_pass_generation.record_id`
  - fixed pass IDs
  - pass output refs
- Trace favors references over payload duplication.

## Fail-closed behavior

Runtime fails closed for:
- malformed input artifact shape
- malformed critique structure
- malformed refinement output shape
- missing required pass or pass ordering mismatch
- final artifact schema validation failure

## Compatibility boundaries

HS-08 integration is intentionally narrow and does **not** redesign:
- routing policy / routing decisions
- prompt registry or alias resolution
- model adapter behavior
- prompt injection defense boundary
- context bundle / trust segmentation / glossary semantics

