# MVP-6: Extraction Eval Gate

Gate-2: Validates extraction phase before paper generation.

## 5 Eval Cases

1. schema_conformance: Both artifacts valid
2. issue_source_traceability: All issues have source_turn_ref
3. agenda_coverage: Agenda items present
4. action_item_completeness: Actions complete
5. replay_consistency: Content hash valid

## Block Condition

Missing source refs, missing agenda items, missing assignees.

## Output

- eval_result × 5
- eval_summary
- evaluation_control_decision (allow/block)
