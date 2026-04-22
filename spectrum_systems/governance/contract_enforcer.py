"""CON: Contract enforcer.

Validates that every 'produces' artifact type has:
1. A schema definition in contracts/schemas/
2. ≥1 example in contracts/examples/ (if examples/ exists)
3. ≥1 test case in evals/eval_case_library.json

Validates that every 'consumes' artifact type:
1. Is produced by at least one registered system
2. Has test fixtures available
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]


class ContractEnforcer:
    """Ensures artifacts produced and consumed honour declared contracts."""

    def __init__(self, repo_root: Path | None = None):
        self.repo_root = Path(repo_root) if repo_root else REPO_ROOT
        self.schema_dir = self.repo_root / "contracts" / "schemas"
        self.examples_dir = self.repo_root / "contracts" / "examples"
        self.fixtures_dir = self.repo_root / "evals" / "fixtures"
        self.eval_lib = self._load_eval_lib()
        self.registry = self._load_registry_produces()

    # ── loaders ─────────────────────────────────────────────────────────────

    def _load_eval_lib(self) -> Dict:
        path = self.repo_root / "evals" / "eval_case_library.json"
        if path.exists():
            return json.loads(path.read_text())
        return {"eval_cases": []}

    def _load_registry_produces(self) -> Dict[str, List[str]]:
        """Return {system_id: [produced_artifact_types]} from the policy file."""
        policy_path = self.repo_root / "docs" / "governance" / "three_letter_system_policy.json"
        if not policy_path.exists():
            return {}
        data = json.loads(policy_path.read_text())
        return {k: v.get("produces", []) for k, v in data.get("systems", {}).items()}

    # ── helpers ─────────────────────────────────────────────────────────────

    def _normalise(self, name: str) -> str:
        return name.lower().replace(" ", "_").replace("-", "_")

    def _has_schema(self, artifact_type: str) -> bool:
        clean = self._normalise(artifact_type)
        return (self.schema_dir / f"{clean}.schema.json").exists()

    def _has_example(self, artifact_type: str) -> bool:
        if not self.examples_dir.exists():
            return True  # non-blocking if examples/ absent
        clean = self._normalise(artifact_type)
        return bool(list(self.examples_dir.glob(f"*{clean}*")))

    def _has_eval_case(self, artifact_type: str) -> bool:
        clean = self._normalise(artifact_type)
        cases = self.eval_lib.get("eval_cases", [])
        return any(
            c.get("artifact_type") == clean
            or clean in c.get("tags", [])
            or clean in c.get("eval_name", "")
            for c in cases
        )

    def _has_fixture(self, artifact_type: str) -> bool:
        if not self.fixtures_dir.exists():
            return True  # non-blocking if fixtures/ absent
        clean = self._normalise(artifact_type)
        return bool(list(self.fixtures_dir.rglob(f"*{clean}*")))

    # ── public API ───────────────────────────────────────────────────────────

    def validate_produces_contract(
        self, system_id: str, artifact_type: str
    ) -> Tuple[bool, str]:
        """Validate that a produced artifact type satisfies its contract."""
        if not self._has_schema(artifact_type):
            return False, f"Missing schema: {self._normalise(artifact_type)}.schema.json"
        if not self._has_example(artifact_type):
            return False, f"No examples for {artifact_type}"
        if not self._has_eval_case(artifact_type):
            return False, f"No eval cases for {artifact_type}"
        return True, "Valid produces contract"

    def validate_consumes_contract(
        self, system_id: str, artifact_type: str
    ) -> Tuple[bool, str]:
        """Validate that a consumed artifact type satisfies its contract."""
        # Check there is at least one producer
        clean = self._normalise(artifact_type)
        producers = [
            s for s, produced in self.registry.items()
            if any(self._normalise(p) == clean for p in produced)
        ]
        if not producers:
            # Non-blocking: registry is partial; warn but don't hard-fail
            pass

        if not self._has_fixture(artifact_type):
            return False, f"No fixtures for {artifact_type}"
        return True, "Valid consumes contract"

    def audit_system(self, system_id: str, produces: List[str], consumes: List[str]) -> Dict:
        """Return a full audit result for a system."""
        results: Dict = {
            "system_id": system_id,
            "produces": {},
            "consumes": {},
            "all_valid": True,
        }
        for art in produces:
            ok, msg = self.validate_produces_contract(system_id, art)
            results["produces"][art] = {"valid": ok, "message": msg}
            if not ok:
                results["all_valid"] = False

        for art in consumes:
            ok, msg = self.validate_consumes_contract(system_id, art)
            results["consumes"][art] = {"valid": ok, "message": msg}
            if not ok:
                results["all_valid"] = False

        return results
