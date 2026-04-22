"""PRM: Prompt admissibility registry.

Only registered prompts may be executed. Unregistered prompt IDs are blocked.
Registration stores the template and its hash; modified templates are also blocked.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Optional


class PromptRegistry:
    """Registry of governed, immutable prompt templates.

    Unregistered prompts and modified templates are blocked from execution.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, Dict] = {}

    def register_prompt(self, prompt_id: str, template: str, metadata: Dict | None = None) -> Dict:
        """Register a prompt template and lock its content hash."""
        content_hash = hashlib.sha256(template.encode()).hexdigest()
        entry = {
            "prompt_id": prompt_id,
            "template": template,
            "template_hash": content_hash,
            "metadata": metadata or {},
        }
        self._registry[prompt_id] = entry
        return entry

    def get_registered_prompt(self, prompt_id: str) -> Optional[Dict]:
        """Return the registered prompt entry or raise ValueError if unregistered."""
        entry = self._registry.get(prompt_id)
        if entry is None:
            raise ValueError(f"Unregistered prompt: '{prompt_id}'")
        return entry

    def verify_prompt_integrity(self, prompt_id: str, template: str) -> bool:
        """Return True only if the template matches the registered hash."""
        entry = self._registry.get(prompt_id)
        if entry is None:
            return False
        current_hash = hashlib.sha256(template.encode()).hexdigest()
        return current_hash == entry["template_hash"]

    def is_registered(self, prompt_id: str) -> bool:
        return prompt_id in self._registry
