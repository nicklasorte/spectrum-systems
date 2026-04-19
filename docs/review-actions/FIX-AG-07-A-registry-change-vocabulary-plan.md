# FIX-AG-07-A Registry Change Vocabulary Plan

Primary prompt type: BUILD

## Scope
Rename AG-07 artifacts/fields away from authority-shaped promotion language to controlled registry-change language, preserve single-path required-eval updates, and fix three fail-closed linkage/replay review issues.

## Steps
1. Rename AG-07 schema/example artifact types and fields/enum values; update standards manifest entries.
2. Rename runtime AG-07 builders/executors and enforce additional fail-closed checks:
   - review-to-request artifact linkage
   - candidate-to-generated-eval linkage before occurrence use
   - expected_outcome reason suffix equals expected_reason_code
3. Update and extend AG-07 tests for renamed surfaces and three review findings.
4. Add a narrow AG-07 local vocabulary guard test covering old forbidden artifact names/fields in AG-07-only files.
5. Update AG-07 runtime documentation to controlled registry-change terminology.
6. Run targeted test and guard commands.
