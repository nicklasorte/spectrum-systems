# SKILL.md — golden-path-check

## Metadata
- **Skill ID**: golden-path-check
- **Type**: VALIDATE
- **Trigger**: Required before marking any VALIDATE step complete
- **Output**: Pass/fail result with validation details

## Purpose
Run the canonical golden-path fixture for a given contract and confirm that the current module implementation produces a valid, schema-conformant output.

The golden path is the minimum happy-path scenario: well-formed input → expected output, no edge cases.
A VALIDATE step that skips the golden path is not complete.

## Inputs
- `CONTRACT_NAME` — the schema name to validate against (e.g., `meeting_minutes_record`, `slide_intelligence_packet`)
- Golden-path example payload from `contracts/examples/<CONTRACT_NAME>.example.json`

## Workflow

1. Locate the golden-path fixture:
   ```
   contracts/examples/<CONTRACT_NAME>.example.json
   ```
   If the fixture does not exist, fail with instructions to create it before running VALIDATE.

2. Load the schema:
   ```python
   from spectrum_systems.contracts import load_schema, validate_artifact
   schema = load_schema("<CONTRACT_NAME>")
   ```

3. Load the golden-path fixture and run validation:
   ```python
   import json
   with open("contracts/examples/<CONTRACT_NAME>.example.json") as f:
       instance = json.load(f)
   validate_artifact(instance, "<CONTRACT_NAME>")
   ```

4. If validation passes:
   - Print `[GOLDEN PATH OK] <CONTRACT_NAME> — fixture is schema-valid.`
   - Exit zero.

5. If validation fails:
   - Print the validation error with field path.
   - Exit non-zero.

## Usage
```bash
.codex/skills/golden-path-check/run.sh meeting_minutes_record
.codex/skills/golden-path-check/run.sh slide_intelligence_packet
```

## Notes
- If no golden-path fixture exists, create one in `contracts/examples/` as part of the BUILD step, not the VALIDATE step.
- The golden-path fixture must represent real, realistic data — not a minimal stub that passes trivially.
- After passing, run the full contract test: `pytest tests/test_contracts.py -k <CONTRACT_NAME>`.
