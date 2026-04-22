"""POL: Policy lifecycle enforcement.

Policies must have created_at, expires_at, and status fields.
Expired or non-active policies are blocked from application.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Tuple


def apply_policy(policy: Dict) -> Tuple[bool, str]:
    """Apply a policy only if it is active and not expired.

    Returns (allowed, reason).
    """
    policy_id = policy.get("policy_id", "unknown")
    status = policy.get("status", "unknown")

    if status != "active":
        return False, f"Policy {policy_id} status is '{status}' (must be 'active')"

    expires_at_raw = policy.get("expires_at")
    if expires_at_raw:
        try:
            # Support both Z-suffix and +00:00 offset
            expires_at_raw = expires_at_raw.replace("Z", "+00:00")
            expires_at = datetime.fromisoformat(expires_at_raw)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                return False, f"Policy {policy_id} expired at {policy.get('expires_at')}"
        except (ValueError, TypeError) as exc:
            return False, f"Policy {policy_id} has invalid expires_at: {exc}"

    return True, f"Policy {policy_id} is active and valid"
