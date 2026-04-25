# Bad Input Campaign Registry

This registry defines adversarial input campaigns for fail-closed validation.

## Required bad-input classes
- conflicting facts
- missing evidence
- low-quality source
- untrusted repo content
- malformed artifact
- partial lineage
- stale policy

All campaign runs must emit `bad_input_campaign_record` artifacts and feed near-miss/failure-mode dashboards.
