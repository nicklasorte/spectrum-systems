"""CON: Registry-to-code drift validator.

Validates that every system in the system registry has:
1. At least one 'owns' responsibility (non-empty owned responsibilities)
2. Every 'produces' artifact type has a schema in contracts/schemas/
3. Every 'consumes' artifact type has ≥1 test case in evals/eval_case_library.json

Emits a registry_drift_report artifact. Exits non-zero if any non-compliance.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]


class RegistryDriftValidator:
    """Validates registry-to-implementation coherence."""

    def __init__(self, repo_root: Path | None = None):
        self.repo_root = Path(repo_root) if repo_root else REPO_ROOT
        self.schema_dir = self.repo_root / "contracts" / "schemas"
        self.schema_names = self._discover_schema_names()
        self.registry = self._parse_registry()
        self.eval_lib = self._load_eval_lib()

    # ── internal loaders ────────────────────────────────────────────────────

    def _parse_registry(self) -> Dict[str, Dict]:
        """Parse docs/architecture/system_registry.md into system definitions."""
        registry_path = self.repo_root / "docs" / "architecture" / "system_registry.md"
        content = registry_path.read_text()
        if "## System Definitions" in content:
            content = content.split("## System Definitions", 1)[1]

        systems: Dict[str, Dict] = {}
        # Split on level-3 headings that look like acronyms (2-8 uppercase chars)
        blocks = re.split(r'\n### ([A-Z][A-Z0-9]{1,7})\b', content)
        # blocks: [preamble, acronym, body, acronym, body, ...]
        i = 1
        while i < len(blocks) - 1:
            acronym = blocks[i].strip()
            body = blocks[i + 1]
            systems[acronym] = self._parse_system_block(acronym, body)
            i += 2

        return systems

    def _discover_schema_names(self) -> set[str]:
        """
        Discover canonical schema names across contracts/schemas recursively.

        This includes nested authority directories (e.g. contracts/schemas/hop/)
        and prevents false negatives from root-only lookup.
        """
        names: set[str] = set()
        if not self.schema_dir.exists():
            return names
        for path in self.schema_dir.rglob("*.schema.json"):
            name = path.name.replace(".schema.json", "")
            if name:
                names.add(name)
        return names

    def _parse_system_block(self, acronym: str, body: str) -> Dict:
        """Extract owns/produces/consumes from a system markdown block."""
        def _extract_list(section: str, text: str) -> List[str]:
            # Negative lookahead (?!\s*\*\*) stops capture at the next **section:** header line.
            pattern = rf'\*\*{section}:\*\*\s*\n((?:\s*-(?!\s*\*\*)[^\n]*\n?)*)'
            m = re.search(pattern, text)
            if not m:
                return []
            lines = [
                re.sub(r'^\s*-\s*`?([^`\n]+)`?', r'\1', ln).strip()
                for ln in m.group(1).splitlines()
                if ln.strip().startswith('-')
            ]
            # Exclude any item containing ** — those are section markers, not artifact names.
            return [l for l in lines if l and '**' not in l]

        return {
            "acronym": acronym,
            "owns": _extract_list("owns", body),
            "produces": _extract_list("produces", body),
            "consumes": _extract_list("consumes", body),
        }

    def _load_eval_lib(self) -> Dict:
        eval_path = self.repo_root / "evals" / "eval_case_library.json"
        if eval_path.exists():
            return json.loads(eval_path.read_text())
        return {"eval_cases": []}

    # ── validation ──────────────────────────────────────────────────────────

    def validate_system(self, system_id: str, system_def: Dict) -> Tuple[bool, List[str]]:
        """Validate single system coherence. Returns (is_valid, errors)."""
        errors: List[str] = []

        # Check 1: has at least one responsibility
        if not system_def.get("owns"):
            errors.append(f"{system_id}: No 'owns' responsibilities defined")

        # Check 2: produces artifacts have schemas
        for artifact_type in system_def.get("produces", []):
            # Normalise: replace spaces with underscores, lower-case
            clean = artifact_type.lower().replace(" ", "_").replace("-", "_")
            if clean not in self.schema_names:
                errors.append(
                    f"{system_id}: produces '{artifact_type}' but no schema "
                    f"'{clean}.schema.json' found in contracts/schemas/"
                )

        # Check 3: consumes artifacts have eval cases
        eval_cases = self.eval_lib.get("eval_cases", [])
        for artifact_type in system_def.get("consumes", []):
            clean = artifact_type.lower().replace(" ", "_").replace("-", "_")
            # Match against artifact_type, tags, or eval_name fields
            matched = any(
                c.get("artifact_type") == clean
                or clean in c.get("tags", [])
                or clean in c.get("eval_name", "")
                for c in eval_cases
            )
            if not matched:
                errors.append(
                    f"{system_id}: consumes '{artifact_type}' but no eval cases "
                    f"in eval_case_library.json"
                )

        return len(errors) == 0, errors

    # ── report emission ─────────────────────────────────────────────────────

    def emit_drift_report(self) -> Dict:
        """Emit registry_drift_report artifact listing validation status of all systems."""
        report: Dict = {
            "artifact_id": f"DRF-{os.urandom(4).hex().upper()}",
            "artifact_type": "registry_drift_report",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "3ls-v1",
            "trace_id": f"TRC-{os.urandom(8).hex().upper()}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "owner_system": "CON",
            "systems_checked": 0,
            "systems_compliant": 0,
            "systems_non_compliant": [],
            "details": {},
        }

        for system_id, system_def in self.registry.items():
            report["systems_checked"] += 1
            is_valid, errors = self.validate_system(system_id, system_def)

            if is_valid:
                report["systems_compliant"] += 1
            else:
                report["systems_non_compliant"].append(system_id)
                report["details"][system_id] = errors

        return report


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    validator = RegistryDriftValidator()
    report = validator.emit_drift_report()
    print(json.dumps(report, indent=2))
    if report["systems_non_compliant"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
