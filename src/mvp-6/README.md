# MVP-6: Extraction Eval Gate

Gate-2 validates extraction phase before paper generation.

## 5 Eval Cases

1. schema_conformance: Both artifacts valid
2. issue_source_traceability: All issues have source_turn_ref (CRITICAL)
3. agenda_coverage: Agenda items present
4. action_item_completeness: Actions have description
5. replay_consistency: Content hash valid

## Block Conditions

Missing source refs, missing agenda items, missing assignees.

## Output

- eval_result × 5
- eval_summary (with pass_rate)
- evaluation_control_decision (allow/block)
- pqx_execution_record

## Integration

Input: minutes_artifact, issue_artifact
Output: If allow → MVP-7 (Structured Issue Set)
        If block → Pipeline halts

## Tests

10 tests covering all eval cases, allow/block decisions, execution records.
