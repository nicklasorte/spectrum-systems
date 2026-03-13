# Error Taxonomy

This taxonomy defines common error categories across automation systems so evaluation harnesses can classify failures consistently.

## Extraction Errors

- Missing entity
- Incorrect mapping
- Partial extraction

## Schema Errors

- Missing required field
- Type mismatch
- Invalid enum value

## Generation Errors

- Low-confidence output
- Hallucinated reference
- Incomplete artifact

## Provenance Errors

- Missing source
- Missing lineage
- Missing review metadata

## Validation Errors

- Failed test case
- Incorrect derived artifact

Evaluation frameworks should tag failures with these categories to focus remediation on the right stage of the pipeline.
