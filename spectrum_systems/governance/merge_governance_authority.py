"""MGV: Merge Governance Authority.

Governs merge decisions with explicit wiring to CDE.
MGV may NOT self-authorize; all decisions flow through CDE.
"""

from __future__ import annotations

from typing import Dict, List, Tuple


class MergeGovernanceAuthority:
    """MGV: Narrowly scoped merge authority — never self-authorizing."""

    def authorize_merge(
        self,
        source_branch: str,
        target_branch: str,
        artifacts: List[str],
        gate_verifier=None,
        cde_reviewer=None,
    ) -> Tuple[bool, Dict]:
        """Authorize a merge only when all gates pass and CDE approves.

        Parameters
        ----------
        source_branch, target_branch:
            The branches involved in the merge.
        artifacts:
            Artifact IDs to verify before merging.
        gate_verifier:
            Callable(artifact_id) → bool. If None, all gates are assumed failed.
        cde_reviewer:
            Callable(decision) → bool. If None, CDE approval is assumed denied.

        Returns
        -------
        (authorized, decision_record)
        """
        decision = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "artifacts": artifacts,
            "authorized_by": "MGV",
            "authorized": True,
            "conditions": [],
        }

        # Gate: verify all artifacts have passed their gates
        for artifact_id in artifacts:
            if gate_verifier is None or not gate_verifier(artifact_id):
                decision["authorized"] = False
                decision["conditions"].append(f"{artifact_id}: gates not verified")

        if not decision["authorized"]:
            return False, decision

        # CRITICAL: MGV cannot self-authorize; route through CDE
        if cde_reviewer is None:
            decision["authorized"] = False
            decision["conditions"].append("CDE reviewer not wired (fail-closed)")
            return False, decision

        cde_ok = cde_reviewer(decision)
        if not cde_ok:
            decision["authorized"] = False
            decision["conditions"].append("CDE rejected the merge decision")
            return False, decision

        return True, decision

    def self_authorize(self, source_branch: str, target_branch: str) -> Tuple[bool, Dict]:
        """Self-authorization is explicitly prohibited. Always returns False."""
        return False, {
            "error": "MGV.self_authorize() is a prohibited operation",
            "reason": "MGV cannot self-authorize; all merge decisions require CDE sign-off",
        }
