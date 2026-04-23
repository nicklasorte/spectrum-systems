"""Fetch PR data from GitHub."""

from typing import List, Dict, Any, Optional
from datetime import datetime


class GitHubClient:
    """Fetch spectrum-systems repo data."""

    def __init__(self, owner: str, repo: str, token: str):
        self.owner = owner
        self.repo = repo
        self.token = token

    def get_merged_prs(self, since: datetime) -> List[Dict[str, Any]]:
        """Get merged PRs since datetime."""
        return []

    def get_pr_by_branch(self, branch: str) -> Optional[Dict[str, Any]]:
        """Get PR for a specific branch."""
        return None
