# GOV-ISO-01 — Governance import isolation review

## Root cause
`run_system_registry_guard.py` imports `spectrum_systems.modules.governance.system_registry_guard` directly, but Python initializes the package `spectrum_systems.modules.governance` first. The package `__init__.py` eagerly imports multiple governance modules including `done_certification`, which imports `jsonschema`. In environments where `jsonschema` is not installed for SRG-only execution, the import fails before SRG logic runs.

So the direct failure cause is eager package import side effects in `spectrum_systems/modules/governance/__init__.py`, not SRG logic itself.

## Additional exposure analysis
The same eager-import pattern can expand hidden dependencies for any script/module importing any symbol under `spectrum_systems.modules.governance.*`, because package initialization executes all eager re-exports first.

This means unrelated governance entrypoints may fail due to optional dependencies used only by other governance modules.

## Import-boundary fix applied
- Make `spectrum_systems/modules/governance/__init__.py` minimal and side-effect free.
- Remove eager re-export imports of governance submodules from package init.
- Preserve explicit dependency ownership in each concrete module (e.g., `done_certification` keeps `jsonschema` requirement).
- Add tests that fail closed if governance package init reintroduces eager imports or if importing SRG side-loads `done_certification`.
