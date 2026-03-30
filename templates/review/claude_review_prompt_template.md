# Claude Review Prompt Template

You are performing an **infrastructure-aware, scoped architecture review** of the
`{{ scope_id }}` subsystem in the `spectrum-systems` repository.

---

## Review Scope

**Scope ID:** `{{ scope_id }}`
**Title:** {{ title }}
**Purpose:** {{ purpose }}
**Golden Path Role:** {{ golden_path_role }}
**Strategy Authority:** `{{ strategy_authority_path }}` (version `{{ strategy_authority_version }}`)

---

## Files in Scope

Review only the following files. Do not make findings about files outside this list
unless they are directly referenced by in-scope files.

{% for f in in_scope_files %}
- `{{ f }}`
{% endfor %}

---

## Related Contracts

The following contract schemas govern inputs and outputs for this subsystem:

{% for c in related_contracts %}
- `{{ c }}`
{% endfor %}

---

## Related Tests

The following test files exercise this subsystem:

{% for t in related_tests %}
- `{{ t }}`
{% endfor %}

---

## Related Design Documents

The following design documents describe the intended behaviour of this subsystem:

{% for d in related_design_docs %}
- `{{ d }}`
{% endfor %}

---

## Source Authorities (Grounding Required)

Use these bounded source authorities while applying strategy constraints:

{% for sa in source_authorities %}
- `{{ sa }}`
{% endfor %}

---

## Known Failure Modes

The following failure modes are known to affect this subsystem. Consider each one
explicitly in your review:

{% for fm in known_failure_modes %}
- `{{ fm }}`
{% endfor %}

---

## System Invariants

The following invariants must hold for this subsystem to be considered correct:

{% for inv in invariants %}
- {{ inv }}
{% endfor %}

---

## Known Edge Cases

The following edge cases are known and must be handled:

{% for ec in known_edge_cases %}
- {{ ec }}
{% endfor %}

---

## Review Instructions

1. **Review only the scoped subsystem** listed in the "Files in Scope" section.
2. **Anchor every finding** to a specific file, contract, test, or design document from
   the lists above. Do not make findings without evidence references.
3. **Emit output matching the review contract schema** at
   `standards/review-contract.schema.json`. Your output must be valid JSON.
4. **Classify every finding** by severity (`critical`, `high`, `medium`, `low`) and
   category (`architecture`, `contract`, `validation`, `alignment`,
   `extraction-quality`, `silent-failure`, `golden-path`, `traceability`, `test`).
5. **Include failure scenarios** in `failure_scenarios[]` for at least the known failure
   modes listed above.
6. **Populate the fix stack** in `priority_fix_stack[]` — ordered list of `finding_id`
   values from most to least urgent.
7. **End with a verdict**: `GO`, `GO_WITH_FIXES`, or `NO_GO`.
   - `GO` — all invariants hold, no critical or high findings
   - `GO_WITH_FIXES` — medium findings only, or high findings with clear, bounded fixes
   - `NO_GO` — critical findings, broken invariants, or systemic traceability failure

---

## Output Format

Emit a single JSON object conforming to `standards/review-contract.schema.json`.

```json
{
  "review_id": "rev-{{ scope_id }}-<YYYY-MM-DD>",
  "scope_id": "{{ scope_id }}",
  "review_type": "architecture",
  "reviewed_at": "<ISO 8601 datetime>",
  "verdict": "GO | GO_WITH_FIXES | NO_GO",
  "findings": [
    {
      "finding_id": "F-001",
      "severity": "high",
      "category": "traceability",
      "title": "<short finding title>",
      "evidence": ["<file or contract path>"],
      "why_it_matters": "<impact explanation>",
      "recommended_fix": "<concrete remediation>",
      "fix_type": "patch | refactor | redesign",
      "downstream_risk": "<risk if unaddressed>",
      "priority_rank": 1
    }
  ],
  "failure_scenarios": [
    {
      "scenario_id": "FS-001",
      "description": "<scenario description>",
      "likelihood": "high | medium | low",
      "impact": "high | medium | low",
      "mitigation": "<mitigation strategy>"
    }
  ],
  "priority_fix_stack": ["F-001", "F-002"],
  "minimum_bar_to_proceed": "<minimum criteria statement>"
}
```
