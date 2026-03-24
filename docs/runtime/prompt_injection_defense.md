# HS-X3 Prompt Injection Defense Layer

HS-X3 hardens the runtime context boundary by adding a deterministic prompt-injection assessment seam between validated `context_bundle` construction and bounded agent execution.

## Detection classes (explicit, bounded)

The detection layer only scans explicit regex classes:

- `override_system_instructions`
- `ignore_prior_instructions_or_policies`
- `reveal_hidden_prompts_or_policies`
- `tool_usage_coercion_outside_rules`

No fuzzy classifier, probabilistic scoring, or model-based adjudication is used in this slice.

## Enforcement actions

The governed `prompt_injection_assessment` artifact emits one of:

- `allow_as_data`
- `quarantine`
- `block_bundle`

Current runtime enforcement behavior:

- `allow_as_data`: runtime proceeds; flagged content remains in context data.
- `quarantine`: runtime blocks before step execution.
- `block_bundle`: runtime blocks before step execution.

## Data-vs-control rule

Flagged instruction-shaped content is preserved as data and never used as a control override surface. HS-X3 enforcement prevents flagged content from mutating:

- routing decision
- prompt resolution
- model adapter behavior
- structured generation requirements
- tool execution permissions

## Policy behavior

Policy surface (`prompt_injection_policy`) is explicit and deterministic:

- `policy_id`
- `require_assessment` (default `true`)
- `on_detection` (`allow_as_data|quarantine|block_bundle`, default `quarantine`)

This cleanly distinguishes:

- suspicious content presence (`detection_status`)
- runtime block/quarantine behavior (`enforcement_action` + runtime gate)

## Fail-closed cases

Runtime fails closed when:

1. assessment is required but not performed,
2. assessment artifact is malformed / contract-invalid,
3. detection/enforcement outcome is internally inconsistent,
4. policy requires block/quarantine but runtime attempts to continue.

## Trace linkage

Traceability is preserved via:

- `prompt_injection_assessment.assessment_id`
- `prompt_injection_assessment.trace` linkage (`trace_id`, `run_id`, source refs)
- `agent_execution_trace.context_source_summary.prompt_injection` summary refs

This allows deterministic reconstruction of whether assessment ran, what was flagged, and what action was enforced.

## Out of scope

- retrieval/ranking redesign
- web/content safety platform expansion
- routing architecture redesign
- broad enterprise security framework changes
