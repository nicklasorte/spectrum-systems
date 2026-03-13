# Comment Resolution Rule Pack (Starter)

This starter pack defines the contract and precedence for SYS-001 rules. It is intentionally minimal so implementation repositories can load these files or mirror their structure without forcing external dependencies.

## Rule File Contract
Each rule entry MUST support:
- `rule_id`: stable identifier.
- `rule_type`: one of `canonical_term`, `issue_pattern`, `disposition`, `drafting`, `validation`, or `profile_override`.
- `priority`: integer where higher runs first within the same type.
- `enabled`: boolean.
- `match`: structured criteria for when the rule applies.
- `action`: structured outcome (normalization, classification, disposition hint, validation failure).
- `rationale_template`: short template explaining the rule.
- `patch_template`: optional patch or text template to apply.
- `source`: origin of the rule (repository path or governing spec).
- `version`: semantic version of the rule definition.

## Precedence
`profile override` > `section-specific rule` > `issue-pattern rule` > `canonical term rule` > `local fallback heuristic`

Local fallbacks remain in implementation repos; this pack establishes the shared layer to be merged later.

## Files
- `canonical_terms.yaml` — normalize terminology and anchors.
- `issue_patterns.yaml` — classify recurring issue forms.
- `disposition_rules.yaml` — guide disposition outcomes.
- `drafting_rules.yaml` — drafting style and tone requirements.
- `validation_rules.yaml` — blocking checks for revision lineage and schema alignment.
- `profiles/default.yaml` — bundles the above with precedence notes.
