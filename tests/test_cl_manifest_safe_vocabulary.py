"""CL-22-FIX regression: CL-added manifest entries must use safe vocabulary.

The standards manifest (`contracts/standards-manifest.json`) is the
canonical artifact registry. It legitimately surfaces authority-owned
artifact types from canonical owners (CDE / GOV / SEL / etc.), so it
is treated as a guard-path file by the authority-shape preflight.

That guard-path classification is *narrow*: every manifest entry
introduced by CL-ALL-01 must still avoid protected non-owner
authority-shape vocabulary (decision / decisions / decided / verdict /
enforcement / enforcement_action / enforce / approval / approved /
promote / promotion / certify / certification). This regression test
makes that narrow rule machine-checked so future CL additions cannot
sneak protected vocabulary in under the manifest's guard-path cover.

The test additionally proves that the authority-shape preflight still
catches the bad case: it scans a synthetic non-guard-path file
containing `allow_decision_proof` and asserts that the preflight
reports the cluster violation. This guarantees the preflight has not
been weakened by this PR.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
VOCAB_PATH = REPO_ROOT / "contracts" / "governance" / "authority_shape_vocabulary.json"
PREFLIGHT_PATH = (
    REPO_ROOT / "spectrum_systems" / "governance" / "authority_shape_preflight.py"
)


# CL-ALL-01 added these artifact_types to the manifest. Every entry's
# fields and values must avoid protected non-owner cluster terms.
CL_INTRODUCED_ARTIFACT_TYPES = frozenset({"core_loop_contract", "core_loop_proof"})

# Single-token protected non-owner cluster terms drawn from
# contracts/governance/authority_shape_vocabulary.json. We hard-code
# them here so that even if the vocabulary file is edited the
# regression still catches the canonical names.
PROTECTED_TOKENS = (
    "decision",
    "decisions",
    "decided",
    "verdict",
    "adjudication",
    "promotion",
    "promoted",
    "promote",
    "certification",
    "certified",
    "certify",
    "enforcement",
    "enforce",
    "enforced",
    "approval",
    "approved",
    "approve",
    "rollback",
    "rolled_back",
    "quarantine",
    "quarantined",
)


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _walk_strings(node):
    """Yield every (string-value, jsonpath) tuple inside a JSON node."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_strings(v)
    elif isinstance(node, str):
        yield node


def _has_protected_token(text: str) -> str | None:
    lowered = text.lower()
    # Token-boundary scan that mirrors how the preflight splits identifiers.
    tokens = {tok for chunk in lowered.replace("/", " ").split() for tok in chunk.split("_")}
    tokens |= {tok for chunk in lowered.split("-") for tok in chunk.split("_")}
    for term in PROTECTED_TOKENS:
        if term in tokens:
            return term
    return None


def test_cl_manifest_entries_use_safe_vocabulary() -> None:
    """Every CL-introduced manifest entry must avoid protected non-owner
    cluster terms in artifact_type, example_path, notes, status, and
    any nested string field.
    """
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = manifest.get("contracts") or []
    cl_entries = [
        e for e in entries if e.get("artifact_type") in CL_INTRODUCED_ARTIFACT_TYPES
    ]
    assert cl_entries, (
        "Expected CL-ALL-01 to register core_loop_contract + core_loop_proof in the manifest"
    )
    bad: list[tuple[str, str, str]] = []
    for entry in cl_entries:
        for value in _walk_strings(entry):
            term = _has_protected_token(value)
            if term:
                bad.append((entry.get("artifact_type", "?"), term, value))
    assert not bad, (
        "CL-introduced manifest entries contain protected non-owner cluster terms. "
        "Use safe vocabulary (signal / result / input / finding / review / advance / readiness):\n"
        + "\n".join(f"  {at}: '{term}' in {val!r}" for at, term, val in bad)
    )


def test_cl_manifest_entries_are_registered() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    types = {e.get("artifact_type") for e in (manifest.get("contracts") or [])}
    missing = CL_INTRODUCED_ARTIFACT_TYPES - types
    assert not missing, f"CL artifact types missing from manifest: {missing}"


def test_authority_shape_preflight_catches_bad_non_owner_artifact(tmp_path: Path) -> None:
    """The preflight must still flag a synthetic bad manifest entry
    containing protected vocabulary (`allow_decision_proof`) when that
    entry lives in a non-guard-path file. This proves the preflight has
    not been weakened by adding the manifest to guard_path_prefixes.
    """
    preflight = _load_module("_cl_authority_preflight", PREFLIGHT_PATH)
    vocab = preflight.load_vocabulary(VOCAB_PATH)

    # Synthetic non-guard-path file under contracts/ that mirrors a
    # manifest fragment using protected vocabulary. The path is
    # deliberately not a guard path, not an owner path, and lives
    # inside contracts/ which is in the default scope.
    synthetic_dir = tmp_path / "contracts" / "standards-manifest-fixture"
    synthetic_dir.mkdir(parents=True)
    synthetic_path = synthetic_dir / "candidate_entry.json"
    synthetic_path.write_text(
        json.dumps(
            {
                "artifact_type": "allow_decision_proof",
                "example_path": "contracts/examples/allow_decision_proof.json",
                "notes": "non-owning support seam invoking decision authority",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    rel_path = "contracts/standards-manifest-fixture/candidate_entry.json"
    violations = preflight.scan_file(synthetic_path, rel_path, vocab)
    symbols = {v.symbol for v in violations}
    assert any("decision" in s for s in symbols), (
        f"Preflight failed to flag protected vocabulary in synthetic non-owner file. "
        f"Symbols seen: {symbols}"
    )


def test_manifest_is_guard_pathed_for_authority_shape_preflight() -> None:
    """contracts/standards-manifest.json must be listed in
    authority_shape_vocabulary.guard_path_prefixes so the canonical
    artifact registry can legitimately reference owner-named artifact
    types without being violated. The other support seams already
    follow this pattern.
    """
    vocab = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    guard_paths = vocab.get("scope", {}).get("guard_path_prefixes") or []
    assert (
        "contracts/standards-manifest.json" in guard_paths
    ), "contracts/standards-manifest.json must be a guard_path_prefix"
    # And the CL delivery report describes the manifest registration in
    # safe vocabulary; it is also guard-pathed.
    assert (
        "docs/reviews/CL_ALL_01_delivery_report.md" in guard_paths
    ), "docs/reviews/CL_ALL_01_delivery_report.md must be a guard_path_prefix"
