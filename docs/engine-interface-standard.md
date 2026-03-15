# Engine Interface Standard

This standard prevents each operational engine from turning into its own incompatible mini-platform as spectrum-systems scales from Level 5 toward Level 7 and beyond. Engines may diverge in domain logic, but their interfaces must stay consistent so orchestration, evaluation, and governance tools can compose them without bespoke glue code. Artifacts can vary; operating patterns should not.

## Canonical engine responsibilities
Every engine must be able to answer these seven questions in a deterministic, documented way:
- **What artifact types do you consume?** Declare contract-backed inputs so upstream systems know how to feed the engine.
- **What artifact types do you emit?** Declare contract-backed outputs so downstream systems can route and validate them.
- **Where do you read inputs from?** Spell out expected locations, mounting conventions, or manifest pointers to avoid path drift.
- **Where do you write outputs?** Use predictable output roots and subdirectories so orchestration and collectors stay stable.
- **How do you validate outputs?** State the contract checks and failure rules to block drift before artifacts propagate.
- **How do you run evaluation fixtures?** Provide a repeatable evaluation hook so engines stay measurable and comparable.
- **What run metadata do you emit?** Publish provenance, contract versions, and run manifests so runs are traceable and reproducible.

These questions underpin orchestration (routing inputs/outputs), evaluation (running fixtures the same way), provenance (linking artifacts to runs and contracts), and governance (enforcing standards across engines).

## Canonical engine contract sections
Each engine must publish an interface document with the following sections and fields:

1) **Engine Identity**
- engine_name
- repo_name
- system_id
- engine_role

2) **Consumed Artifacts**
- artifact_class
- artifact_type
- contract_name
- contract_version

3) **Emitted Artifacts**
- artifact_class
- artifact_type
- contract_name
- contract_version

4) **CLI Interface**
- command pattern
- required flags
- optional flags

5) **Output Structure**
- output directory convention
- required output files
- validation report location
- run manifest location

6) **Validation Behavior**
- contract validation required
- fail-fast rules
- schema resolution expectations

7) **Evaluation Hooks**
- fixture root convention
- evaluation command pattern
- evaluation report output

8) **Provenance / Run Metadata**
- engine_version
- timestamp
- input artifact references
- output artifact references
- contract versions used
- status
- error notes if applicable

9) **Failure Reporting**
- deterministic error structure
- human-readable notes
- machine-readable status file

## Canonical CLI conventions
Engines should expose a predictable CLI so orchestration can call any engine with minimal adaptation. Preferred pattern:

```
python -m <engine_module> run \
  --inputs <path_to_inputs_or_manifest> \
  --output-dir <path_to_output_root> \
  --run-manifest <path_to_run_manifest> \
  --validate \
  --eval-fixtures <path_to_eval_root> \
  [--config <path_to_config>] \
  [--dry-run]
```

CLI expectations:
- Use `run` as the primary subcommand; avoid bespoke verbs.
- Inputs should accept either a path or manifest pointer; document precedence.
- Outputs should default to a deterministic root and expose flags to override.
- Validation is on by default; `--no-validate` should be explicit and rare.
- Evaluation flags should run fixtures in-place and emit a report under the output root.
- Errors must exit non-zero, emit the deterministic status file, and surface a concise human-readable note.

## Governance Artifact Access
Engines must resolve governance artifacts (schemas, contracts, registry files, standards manifests) from a local schema root path provided at runtime. A canonical flag pattern is `--schema-root ../spectrum-systems/governance/schemas`. Engines must not fetch governance artifacts over the network and should fail clearly when the schema root cannot be found.

## Registry tagging
Engines that are expected to conform to this standard are marked with `interface_standard_expected = true` in the System Registry (`docs/system-registry.md`). That flag gives orchestrators and compliance checks a single place to see which systems must present the canonical interface.
