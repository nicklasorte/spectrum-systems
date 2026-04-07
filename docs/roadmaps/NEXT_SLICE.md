# Next Recommended Slice

## BATCH-GOV-FIX-03 — CI Drift Gate for Registry-Covered Prompt Surfaces

Add a dedicated CI gate that triggers on registry-covered governed prompt paths and enforces:
- `python scripts/check_governance_compliance.py --file <changed-governed-file>` for each changed governed prompt file,
- `pytest tests/test_governed_prompt_surface_sync.py` as the taxonomy coherence gate.

### Outcome target
- Detects governed prompt surface drift at PR time with explicit, narrow feedback.
- Preserves fail-closed behavior while keeping governance checks lightweight and repo-native.
