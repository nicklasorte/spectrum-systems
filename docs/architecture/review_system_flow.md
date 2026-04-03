# Governed Review System Flow

1. Build/runtime event emits post-execution and loop-control artifacts.
2. `review_trigger_policy` deterministically evaluates lineage + policy.
3. Trigger artifact includes typed `review_request` when review is required.
4. Claude/Codex review output is captured as governed review artifact.
5. `review_signal_extractor` produces `review_control_signal` (typed, fail-closed).
6. `review_eval_bridge` emits review-derived `eval_result` + observability artifacts.
7. `evaluation_control` consumes replay/eval/review signals and enforces required-review gates.
8. Control emits the sole authority decision (`evaluation_control_decision`).

## Principle
- Review generates perspective.
- Eval translates perspective into governed signals.
- Control remains the only authority.
