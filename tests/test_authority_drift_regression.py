"""EVL regression coverage for AUTH-01 authority drift detection.

Each historical SHADOW_OWNERSHIP_OVERLAP pattern is captured as a parametrized
case. The contract is:

  1. ``detect_authority_drift`` flags the pattern.
  2. ``apply_authority_repair`` rewrites it.
  3. The repaired text is clean (no further drift findings).

Together these enforce that every failure becomes deterministic regression
coverage, with no manual remediation required.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from spectrum_systems.guards.authority_linter import (
    AuthorityLinterError,
    REASON_CODE,
    detect_authority_drift,
    apply_authority_repair,
    is_clean,
    load_authority_matrix,
)
from spectrum_systems.modules.runtime.authority_drift_preflight import (
    AuthorityDriftBlocked,
    run_preflight,
)
from spectrum_systems.modules.runtime.authority_repair_engine import (
    repair_authority_drift,
    repair_text,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---- Known bad patterns ----------------------------------------------------

BAD_PATTERNS = [
    ("GOV decides", "GOV", "decides", "CDE"),
    ("PRA approves", "PRA", "approves", "CDE"),
    ("TLC enforces", "TLC", "enforces", "SEL"),
    ("TPA executes", "TPA", "executes", "PQX"),
    ("TLC adjudicates", "TLC", "adjudicates", "TPA"),
    ("TLC decides", "TLC", "decides", "CDE"),
    ("GOV approves", "GOV", "approves", "CDE"),
    ("POL decides", "POL", "decides", "CDE"),
    ("POL executes", "POL", "executes", "PQX"),
    ("PRA decides", "PRA", "decides", "CDE"),
    ("TPA promotes", "TPA", "promotes", "CDE"),
    ("GOV determines", "GOV", "determines", "CDE"),
]


@pytest.mark.parametrize("phrase,system,verb,canonical_owner", BAD_PATTERNS)
def test_linter_detects_known_bad_pattern(
    phrase: str, system: str, verb: str, canonical_owner: str
) -> None:
    findings = detect_authority_drift(phrase)
    assert findings, f"linter missed drift in {phrase!r}"
    finding = findings[0]
    assert finding["reason_code"] == REASON_CODE
    assert finding["system"] == system
    assert finding["verb"] == verb
    assert finding["canonical_owner"] == canonical_owner
    assert finding["match"] == phrase
    assert canonical_owner in finding["suggested_fix"]


@pytest.mark.parametrize("phrase,system,verb,canonical_owner", BAD_PATTERNS)
def test_repair_fixes_known_bad_pattern(
    phrase: str, system: str, verb: str, canonical_owner: str
) -> None:
    repaired, findings = repair_text(phrase)
    assert findings, "expected findings for input"
    assert repaired != phrase
    assert canonical_owner in repaired
    # Idempotency: re-running repair must not change a clean text.
    repaired_again, follow_up = repair_text(repaired)
    assert follow_up == [], f"residual drift after repair: {follow_up}"
    assert repaired_again == repaired


@pytest.mark.parametrize("phrase,system,verb,canonical_owner", BAD_PATTERNS)
def test_repaired_text_passes_linter(
    phrase: str, system: str, verb: str, canonical_owner: str
) -> None:
    repaired, _ = repair_text(phrase)
    assert is_clean(repaired)


# ---- Allowed-verb attributions remain clean --------------------------------

CLEAN_PATTERNS = [
    "TLC routes and records lineage",
    "TPA adjudicates policy",
    "CDE decides closure",
    "GOV certifies evidence",
    "PRA provides promotion readiness inputs",
    "POL governs policy state",
]


@pytest.mark.parametrize("phrase", CLEAN_PATTERNS)
def test_canonical_phrasings_are_clean(phrase: str) -> None:
    assert detect_authority_drift(phrase) == []
    assert is_clean(phrase)


# ---- Sentence-level drift ---------------------------------------------------


def test_full_sentence_drift_detected_and_repaired() -> None:
    text = (
        "When admission lands, TLC enforces policy gates and GOV decides "
        "promotion. Then PRA approves the artifact for release."
    )
    findings = detect_authority_drift(text)
    assert {f["match"] for f in findings} >= {
        "TLC enforces",
        "GOV decides",
        "PRA approves",
    }
    repaired = apply_authority_repair(text, findings)
    assert is_clean(repaired)
    # Original spans are gone; canonical owners appear.
    assert "TLC enforces" not in repaired
    assert "GOV decides" not in repaired
    assert "PRA approves" not in repaired
    assert "SEL enforces" in repaired
    assert "CDE decides" in repaired


# ---- Matrix integrity -------------------------------------------------------


def test_matrix_loads_and_has_required_systems() -> None:
    matrix = load_authority_matrix()
    required = {"CDE", "GOV", "TPA", "TLC", "PRA", "POL"}
    assert required.issubset(matrix["systems"].keys())
    for system in required:
        record = matrix["systems"][system]
        assert isinstance(record.get("allowed_verbs"), list)
        assert isinstance(record.get("forbidden_verbs"), list)


def test_matrix_failure_is_fail_closed(tmp_path: Path) -> None:
    bogus = tmp_path / "missing.yaml"
    with pytest.raises(AuthorityLinterError):
        load_authority_matrix(bogus)


# ---- Repair engine artifact shape ------------------------------------------


def test_repair_artifact_shape_for_dirty_file(tmp_path: Path) -> None:
    target = tmp_path / "drifty_doc.md"
    target.write_text("TLC enforces things and GOV decides outcomes.\n", encoding="utf-8")
    artifact = repair_authority_drift(target, now="2026-04-25T00:00:00+00:00")
    assert artifact["artifact_type"] == "repair_plan_artifact"
    assert artifact["repair_plan"]["finding_count"] == 2
    assert artifact["repair_plan"]["deterministic"] is True
    assert artifact["repair_plan"]["input_hash"] != artifact["repair_plan"]["output_hash"]
    assert artifact["authority_repair_diff"]


def test_repair_artifact_shape_for_clean_file(tmp_path: Path) -> None:
    target = tmp_path / "clean_doc.md"
    target.write_text("TLC routes and records lineage.\n", encoding="utf-8")
    artifact = repair_authority_drift(target, now="2026-04-25T00:00:00+00:00")
    assert artifact["repair_plan"]["finding_count"] == 0
    assert artifact["authority_repair_diff"] == ""
    assert artifact["repair_plan"]["input_hash"] == artifact["repair_plan"]["output_hash"]


# ---- Preflight gate --------------------------------------------------------


def test_preflight_passes_for_clean_in_scope_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Use a real in-scope path under tests/ so the preflight gate engages.
    rel = "tests/_tmp_authority_clean.py"
    full = REPO_ROOT / rel
    full.write_text("# TLC routes and records lineage.\n", encoding="utf-8")
    try:
        result = run_preflight([rel])
        assert result["status"] == "pass"
        assert result["finding_count"] == 0
    finally:
        full.unlink(missing_ok=True)


def test_preflight_blocks_for_drifty_in_scope_file() -> None:
    rel = "tests/_tmp_authority_drift.py"
    full = REPO_ROOT / rel
    full.write_text("# TLC enforces and GOV decides.\n", encoding="utf-8")
    try:
        result = run_preflight([rel])
        assert result["artifact_type"] == "authority_drift_block_record"
        assert result["status"] == "halt"
        assert result["reason_code"] == "SHADOW_OWNERSHIP_OVERLAP"
        assert result["finding_count"] == 2

        with pytest.raises(AuthorityDriftBlocked) as excinfo:
            run_preflight([rel], raise_on_block=True)
        assert excinfo.value.record["status"] == "halt"
    finally:
        full.unlink(missing_ok=True)


def test_preflight_skips_out_of_scope_paths() -> None:
    # docs/architecture/ is intentionally out of preflight scope.
    rel = "docs/architecture/_tmp_authority.md"
    full = REPO_ROOT / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text("TLC enforces something — out of preflight scope.\n", encoding="utf-8")
    try:
        result = run_preflight([rel])
        assert result["status"] == "pass"
        assert result["finding_count"] == 0
    finally:
        full.unlink(missing_ok=True)


# ---- Import-boundary regression (AUTH-01F) ---------------------------------


_BOUNDARY_PROBE = """
import sys
import spectrum_systems.guards.authority_linter as lin
import scripts.run_authority_drift_guard  # noqa: F401

forbidden = [
    "spectrum_systems.modules.runtime",
    "spectrum_systems.modules.runtime.run_bundle",
    "jsonschema",
]
loaded = [name for name in forbidden if name in sys.modules]
print("LOADED:" + ",".join(loaded))
print("MATRIX_OK:" + str(bool(lin.load_authority_matrix())))
"""


def test_drift_guard_does_not_import_runtime_or_jsonschema() -> None:
    """The lightweight guard path must not pull runtime/__init__ or jsonschema.

    Spawns a fresh interpreter so cached modules from the test process do not
    mask a regression. Asserts that ``run_bundle`` and ``jsonschema`` are
    absent from ``sys.modules`` after importing the guard script and the
    lightweight linter.
    """
    proc = subprocess.run(
        [sys.executable, "-c", _BOUNDARY_PROBE],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"probe failed: {proc.stderr}"
    out = proc.stdout
    assert "LOADED:\n" in out + "\n", f"forbidden modules loaded; stdout={out!r}"
    assert "MATRIX_OK:True" in out


def test_minimal_yaml_loader_handles_matrix_without_pyyaml() -> None:
    """The bundled stdlib YAML loader can parse the canonical matrix.

    Spawns a fresh interpreter with PyYAML hidden via an ``yaml`` import shim
    that raises ``ImportError``, then asserts the matrix still loads with the
    expected systems. This guards against the lightweight loader silently
    requiring PyYAML in CI environments that lack it.
    """
    probe = """
import sys
class _Block:
    def find_module(self, name, path=None): return self if name == 'yaml' else None
    def load_module(self, name): raise ImportError('yaml hidden for test')
sys.meta_path.insert(0, _Block())
sys.modules.pop('yaml', None)
from spectrum_systems.guards.authority_linter import load_authority_matrix
m = load_authority_matrix()
required = {'CDE','GOV','TPA','TLC','PRA','POL'}
missing = sorted(required - set(m['systems'].keys()))
print('MISSING:' + ','.join(missing))
print('TLC_FORBIDDEN:' + ','.join(sorted(m['systems']['TLC'].get('forbidden_verbs', []))))
print('OWNS_DECIDES:' + str(m['canonical_verb_owners'].get('decides')))
"""
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"probe failed: {proc.stderr}"
    assert "MISSING:\n" in proc.stdout + "\n", proc.stdout
    assert "TLC_FORBIDDEN:adjudicates,decides,enforces" in proc.stdout
    assert "OWNS_DECIDES:CDE" in proc.stdout
