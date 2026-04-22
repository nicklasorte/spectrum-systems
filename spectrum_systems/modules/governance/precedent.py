"""PRX: Precedent eligibility — scope-match enforcement.

retrieve_precedent() returns a precedent only when the calling context_class
is in the precedent's applicable_to_classes list.
"""

from __future__ import annotations

from typing import Dict, Optional


def retrieve_precedent(precedent: Dict, context_class: str) -> Optional[Dict]:
    """Return precedent only if context_class is in its applicable scope.

    Returns None when the precedent does not apply to the given context class.
    """
    allowed_classes = precedent.get("applicable_to_classes", [])
    if context_class not in allowed_classes:
        return None
    return precedent
