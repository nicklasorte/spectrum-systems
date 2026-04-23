"""Deprecation layer for 3LS simplification backward compatibility (Phase 8).

Old system names → new consolidated system names.
All old entry points work during the migration window with deprecation warnings.

Migration timeline:
  Week 1-2: Deprecation warnings (current)
  Week 3-4: Deprecation errors (fail-closed)
  Week 5+:  Old code removed

Old → New mapping:
  TLC + GOV  → GOVERN  (spectrum_systems.govern.govern.GOVERNSystem)
  TPA + PRG  → EXEC    (spectrum_systems.exec_system.exec_system.EXECSystem)
  WPG + CHK  → EVAL    (spectrum_systems.eval_system.eval_system.EVALSystem)
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Tuple


_DEPRECATION_WARNINGS: Dict[str, str] = {
    "wpg_gate": "wpg_gate() is deprecated. Use EVALSystem.eval_gate() instead.",
    "tpa_check": "tpa_check() is deprecated. Use EXECSystem.exec_check() instead.",
    "tlc_route": "tlc_route() is deprecated. Use GOVERNSystem.route_artifact() instead.",
    "gov_policy": "gov_policy() is deprecated. Use GOVERNSystem.policy_check() instead.",
    "prg_roadmap": "prg_roadmap() is deprecated. Use EXECSystem.roadmap_alignment_check() instead.",
    "chk_batch": "chk_batch() is deprecated. Use EVALSystem.batch_constraint_check() instead.",
    "chk_umbrella": "chk_umbrella() is deprecated. Use EVALSystem.umbrella_constraint_check() instead.",
    "wkg_provenance": "wkg_provenance() is deprecated. Use EVALSystem.validate_provenance() instead.",
    "tlc_lifecycle": "tlc_lifecycle() is deprecated. Use GOVERNSystem.lifecycle_check() instead.",
    "prg_priority_report": "prg_priority_report() is deprecated. Use EXECSystem.generate_priority_report() instead.",
}


def _warn_deprecated(method_name: str) -> None:
    msg = _DEPRECATION_WARNINGS.get(
        method_name,
        f"{method_name}() is deprecated. Use the consolidated GOVERN/EXEC/EVAL system instead.",
    )
    warnings.warn(msg, DeprecationWarning, stacklevel=3)


class DeprecationLayer:
    """Backward-compatible wrapper for old system names.

    During the migration window, old callers can use this class
    to access the consolidated systems without changing call sites.

    Usage (old code — still works):
        compat = DeprecationLayer()
        allowed, reason = compat.tpa_check(artifact)  # → EXECSystem.exec_check

    Usage (new code — preferred):
        from spectrum_systems.exec_system import EXECSystem
        exec_sys = EXECSystem()
        allowed, reason = exec_sys.exec_check(artifact)
    """

    def __init__(self, event_log: Optional[Any] = None) -> None:
        self._event_log = event_log
        self._govern: Optional[Any] = None
        self._exec: Optional[Any] = None
        self._eval: Optional[Any] = None

    def _get_govern(self) -> Any:
        if self._govern is None:
            from spectrum_systems.govern.govern import GOVERNSystem
            self._govern = GOVERNSystem(event_log=self._event_log)
        return self._govern

    def _get_exec(self) -> Any:
        if self._exec is None:
            from spectrum_systems.exec_system.exec_system import EXECSystem
            self._exec = EXECSystem(event_log=self._event_log)
        return self._exec

    def _get_eval(self) -> Any:
        if self._eval is None:
            from spectrum_systems.eval_system.eval_system import EVALSystem
            self._eval = EVALSystem(event_log=self._event_log)
        return self._eval

    # ------------------------------------------------------------------
    # Old TPA entry points → EXEC
    # ------------------------------------------------------------------

    def tpa_check(self, artifact: Dict[str, Any]) -> Tuple[bool, str]:
        """[DEPRECATED] Use EXECSystem.exec_check() instead."""
        _warn_deprecated("tpa_check")
        return self._get_exec().exec_check(artifact)

    def tpa_lineage(self, artifact_id: str, refs: List[str]) -> Tuple[bool, str]:
        """[DEPRECATED] Use EXECSystem.validate_lineage() instead."""
        _warn_deprecated("tpa_check")
        return self._get_exec().validate_lineage(artifact_id, refs)

    def tpa_scope(self, artifact: Dict[str, Any]) -> Tuple[bool, str]:
        """[DEPRECATED] Use EXECSystem.trust_scope_check() instead."""
        _warn_deprecated("tpa_check")
        return self._get_exec().trust_scope_check(artifact)

    # ------------------------------------------------------------------
    # Old PRG entry points → EXEC
    # ------------------------------------------------------------------

    def prg_roadmap(self, artifact: Dict[str, Any], items: Optional[List[str]] = None) -> Tuple[bool, str]:
        """[DEPRECATED] Use EXECSystem.roadmap_alignment_check() instead."""
        _warn_deprecated("prg_roadmap")
        return self._get_exec().roadmap_alignment_check(artifact, items)

    def prg_priority_report(self, health: str, metrics: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """[DEPRECATED] Use EXECSystem.generate_priority_report() instead."""
        _warn_deprecated("prg_priority_report")
        return self._get_exec().generate_priority_report(health, metrics)

    # ------------------------------------------------------------------
    # Old TLC entry points → GOVERN
    # ------------------------------------------------------------------

    def tlc_route(self, artifact: Dict[str, Any], registry: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
        """[DEPRECATED] Use GOVERNSystem.route_artifact() instead."""
        _warn_deprecated("tlc_route")
        return self._get_govern().route_artifact(artifact, registry)

    def tlc_lifecycle(self, artifact: Dict[str, Any], target: str) -> Tuple[bool, str]:
        """[DEPRECATED] Use GOVERNSystem.lifecycle_check() instead."""
        _warn_deprecated("tlc_lifecycle")
        return self._get_govern().lifecycle_check(artifact, target)

    # ------------------------------------------------------------------
    # Old GOV entry points → GOVERN
    # ------------------------------------------------------------------

    def gov_policy(self, artifact: Dict[str, Any], ref: Optional[str] = None) -> Tuple[bool, str]:
        """[DEPRECATED] Use GOVERNSystem.policy_check() instead."""
        _warn_deprecated("gov_policy")
        return self._get_govern().policy_check(artifact, ref)

    def gov_drift(self, declared: Dict[str, Any], observed: Dict[str, Any]) -> Dict[str, Any]:
        """[DEPRECATED] Use GOVERNSystem.detect_policy_drift() instead."""
        _warn_deprecated("gov_policy")
        return self._get_govern().detect_policy_drift(declared, observed)

    # ------------------------------------------------------------------
    # Old WPG entry points → EVAL
    # ------------------------------------------------------------------

    def wpg_gate(self, artifact: Dict[str, Any], results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """[DEPRECATED] Use EVALSystem.eval_gate() instead."""
        _warn_deprecated("wpg_gate")
        return self._get_eval().eval_gate(artifact, results)

    def wkg_provenance(self, artifact: Dict[str, Any]) -> Tuple[bool, str]:
        """[DEPRECATED] Use EVALSystem.validate_provenance() instead."""
        _warn_deprecated("wkg_provenance")
        return self._get_eval().validate_provenance(artifact)

    # ------------------------------------------------------------------
    # Old CHK entry points → EVAL
    # ------------------------------------------------------------------

    def chk_batch(self, artifact: Dict[str, Any]) -> Tuple[bool, str]:
        """[DEPRECATED] Use EVALSystem.batch_constraint_check() instead."""
        _warn_deprecated("chk_batch")
        return self._get_eval().batch_constraint_check(artifact)

    def chk_umbrella(self, artifact: Dict[str, Any]) -> Tuple[bool, str]:
        """[DEPRECATED] Use EVALSystem.umbrella_constraint_check() instead."""
        _warn_deprecated("chk_umbrella")
        return self._get_eval().umbrella_constraint_check(artifact)
