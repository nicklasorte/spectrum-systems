"""Regression tests for RFX-03F authority-guard fix.

Covers:
  - The three new RFX guard modules use authority-neutral docstrings/comments
    so the System Registry Guard (SRG) does not raise SHADOW_OWNERSHIP_OVERLAP
    or PROTECTED_AUTHORITY_VIOLATION on them.
  - Common English uppercase words like ``NOT``, ``AND``, and ``ALL`` are not
    treated as 3-letter system symbols when they appear next to owner-claim
    verbs.
  - Real protected-authority drift (e.g. a non-owner claiming a registered
    system's responsibility) is still caught by the SRG.

These guards are stateless. They are exercised here by feeding synthetic
file contents through ``evaluate_system_registry_guard`` directly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.governance.system_registry_guard import (
    evaluate_system_registry_guard,
    load_guard_policy,
    parse_system_registry,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "contracts" / "governance" / "system_registry_guard_policy.json"
REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "system_registry.md"

RFX_GUARD_MODULES = (
    "spectrum_systems/modules/runtime/rfx_certification_gate.py",
    "spectrum_systems/modules/runtime/rfx_decision_bridge_guard.py",
    "spectrum_systems/modules/runtime/rfx_integrity_bundle.py",
)


@pytest.fixture(scope="module")
def policy() -> dict:
    return load_guard_policy(POLICY_PATH)


@pytest.fixture(scope="module")
def registry_model():
    return parse_system_registry(REGISTRY_PATH)


def _evaluate(changed_files: list[str], policy: dict, registry_model) -> dict:
    return evaluate_system_registry_guard(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        policy=policy,
        registry_model=registry_model,
    )


# ---------------------------------------------------------------------------
# Authority-neutral RFX guard modules pass SRG cleanly
# ---------------------------------------------------------------------------

class TestRFXGuardModulesAreAuthorityNeutral:
    @pytest.mark.parametrize("rel_path", RFX_GUARD_MODULES)
    def test_module_does_not_trigger_shadow_ownership_overlap(
        self, rel_path: str, policy: dict, registry_model
    ) -> None:
        result = _evaluate([rel_path], policy, registry_model)
        offending = [
            d
            for d in result["diagnostics"]
            if d.get("file") == rel_path
            and d.get("reason_code") == "SHADOW_OWNERSHIP_OVERLAP"
        ]
        assert offending == [], (
            f"{rel_path} produced SHADOW_OWNERSHIP_OVERLAP diagnostics: {offending}"
        )

    @pytest.mark.parametrize("rel_path", RFX_GUARD_MODULES)
    def test_module_does_not_trigger_protected_authority_violation(
        self, rel_path: str, policy: dict, registry_model
    ) -> None:
        result = _evaluate([rel_path], policy, registry_model)
        offending = [
            d
            for d in result["diagnostics"]
            if d.get("file") == rel_path
            and d.get("reason_code") == "PROTECTED_AUTHORITY_VIOLATION"
        ]
        assert offending == [], (
            f"{rel_path} produced PROTECTED_AUTHORITY_VIOLATION diagnostics: "
            f"{offending}"
        )

    def test_full_rfx_guard_module_set_passes(
        self, policy: dict, registry_model
    ) -> None:
        result = _evaluate(list(RFX_GUARD_MODULES), policy, registry_model)
        assert result["status"] == "pass", (
            f"SRG should pass on RFX guard module set; got reason_codes="
            f"{result['normalized_reason_codes']!r}, "
            f"diagnostics={result['diagnostics']!r}"
        )


# ---------------------------------------------------------------------------
# Common English uppercase words must not be treated as 3-letter systems
# ---------------------------------------------------------------------------

class TestCommonUppercaseWordsAreNotSystemSymbols:
    @pytest.mark.parametrize(
        "english_word",
        ["NOT", "AND", "BUT", "FOR", "ALL", "ANY", "NEW", "OUT"],
    )
    def test_uppercase_english_word_in_policy_exemption(
        self, english_word: str, policy: dict
    ) -> None:
        exempt = {
            str(item).upper()
            for item in (policy.get("non_system_uppercase_tokens") or [])
        }
        assert english_word in exempt, (
            f"{english_word!r} must be exempted from 3-letter system-symbol "
            "detection by SRG policy"
        )

    def test_does_not_phrase_does_not_produce_shadow_overlap(
        self, policy: dict, registry_model, tmp_path: Path
    ) -> None:
        # Create a synthetic Python file under spectrum_systems/modules/runtime/
        # so SRG actually scans it. We simulate by writing into a temp shadow
        # path placed inside the repo.
        synth_dir = REPO_ROOT / "spectrum_systems" / "modules" / "runtime"
        synth_path = synth_dir / "_rfx_synthetic_neutral_wording_for_test.py"
        synth_path.write_text(
            '"""Synthetic module — does NOT issue closure decisions.\n'
            "\n"
            "This guard does NOT introduce a new authority. It only verifies\n"
            "that an evidence record is present.\n"
            '"""\n',
            encoding="utf-8",
        )
        try:
            rel = "spectrum_systems/modules/runtime/_rfx_synthetic_neutral_wording_for_test.py"
            result = _evaluate([rel], policy, registry_model)
            offending = [
                d
                for d in result["diagnostics"]
                if d.get("symbol") == "NOT"
            ]
            assert offending == [], (
                f"NOT must not be flagged as a system symbol; got: {offending}"
            )
        finally:
            synth_path.unlink()

    def test_not_a_new_authority_phrase_does_not_flag_not(
        self, policy: dict, registry_model
    ) -> None:
        synth_dir = REPO_ROOT / "spectrum_systems" / "modules" / "runtime"
        synth_path = synth_dir / "_rfx_synthetic_not_a_new_authority_for_test.py"
        synth_path.write_text(
            '"""Synthetic module — not a new authority.\n'
            "\n"
            "Implementation notes only; does not assign canonical roles.\n"
            '"""\n',
            encoding="utf-8",
        )
        try:
            rel = "spectrum_systems/modules/runtime/_rfx_synthetic_not_a_new_authority_for_test.py"
            result = _evaluate([rel], policy, registry_model)
            # No SHADOW_OWNERSHIP_OVERLAP or PROTECTED_AUTHORITY_VIOLATION on NOT.
            offending = [
                d
                for d in result["diagnostics"]
                if d.get("symbol") == "NOT"
            ]
            assert offending == [], (
                f"'not a new authority' must not flag NOT as a system; got: {offending}"
            )
        finally:
            synth_path.unlink()


# ---------------------------------------------------------------------------
# Real protected-authority drift must still be caught
# ---------------------------------------------------------------------------

class TestRealOwnershipDriftStillCaught:
    """Synthetic non-owner claims of registered ownership must still be flagged."""

    def test_gov_decides_readiness_is_still_caught(
        self, policy: dict, registry_model
    ) -> None:
        # GOV is registered, but readiness is canonically the closure
        # decision contributor's responsibility (CDE per the registry).
        # GOV claiming to "decide readiness" must still be flagged.
        synth_dir = REPO_ROOT / "spectrum_systems" / "modules" / "runtime"
        synth_path = synth_dir / "_rfx_synthetic_real_drift_for_test.py"
        synth_path.write_text(
            '"""Synthetic drift sample.\n'
            "\n"
            "GOV decides readiness and owns the closure decision.\n"
            '"""\n',
            encoding="utf-8",
        )
        try:
            rel = "spectrum_systems/modules/runtime/_rfx_synthetic_real_drift_for_test.py"
            result = _evaluate([rel], policy, registry_model)
            assert result["status"] == "fail", (
                "Real drift ('GOV decides readiness and owns the closure "
                "decision') must still be caught"
            )
            offending = {d.get("reason_code") for d in result["diagnostics"]}
            assert (
                "SHADOW_OWNERSHIP_OVERLAP" in offending
                or "DIRECT_OWNERSHIP_OVERLAP" in offending
                or "PROTECTED_AUTHORITY_VIOLATION" in offending
            ), f"Expected ownership-overlap diagnostic; got reason_codes={offending}"
        finally:
            synth_path.unlink()

    def test_non_owner_claims_enforcement_still_caught(
        self, policy: dict, registry_model
    ) -> None:
        # PQX is a registered system but enforcement is canonically SEL's.
        # A claim like "PQX owns enforcement" must be flagged.
        synth_dir = REPO_ROOT / "spectrum_systems" / "modules" / "runtime"
        synth_path = synth_dir / "_rfx_synthetic_pqx_enforcement_drift_for_test.py"
        synth_path.write_text(
            '"""Synthetic drift sample.\n'
            "\n"
            "PQX owns enforcement and has authority over fail-closed actions.\n"
            '"""\n',
            encoding="utf-8",
        )
        try:
            rel = "spectrum_systems/modules/runtime/_rfx_synthetic_pqx_enforcement_drift_for_test.py"
            result = _evaluate([rel], policy, registry_model)
            assert result["status"] == "fail", (
                "Real drift ('PQX owns enforcement') must still be caught"
            )
            offending = {d.get("reason_code") for d in result["diagnostics"]}
            assert (
                "SHADOW_OWNERSHIP_OVERLAP" in offending
                or "DIRECT_OWNERSHIP_OVERLAP" in offending
            ), f"Expected ownership-overlap diagnostic; got reason_codes={offending}"
        finally:
            synth_path.unlink()


# ---------------------------------------------------------------------------
# RFX wording invariants in the live source files
# ---------------------------------------------------------------------------

class TestRFXGuardSourceWordingInvariants:
    """Static checks that catch reintroduction of authority-claim phrasing."""

    BANNED_PHRASES = (
        "is the authority",
        "remains the sole",
        "decision authority",
        "enforcement authority",
        "policy authority",
        "lineage authority",
        "replay authority",
        "certification packaging authority",
        "decide readiness",
        "GOV does NOT",
        "GOV certification withheld",
        "GOV certification hard gate",
    )

    @pytest.mark.parametrize("rel_path", RFX_GUARD_MODULES)
    def test_no_banned_phrase_in_module(self, rel_path: str) -> None:
        path = REPO_ROOT / rel_path
        text = path.read_text(encoding="utf-8")
        present = [phrase for phrase in self.BANNED_PHRASES if phrase in text]
        assert not present, (
            f"{rel_path} contains banned authority-claim phrases: {present}"
        )
