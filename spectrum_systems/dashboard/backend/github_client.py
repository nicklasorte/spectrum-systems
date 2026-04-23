"""Fetch PR data from GitHub to link to batches."""

import requests
from typing import List, Dict, Any, Optional
from datetime import datetime


class GitHubClient:
    """Fetch spectrum-systems repo data."""

    def __init__(self, owner: str, repo: str, token: str):
        self.owner = owner
        self.repo = repo
        self.token = token
        self.base_url = 'https://api.github.com'

    def get_merged_prs(self, since: datetime) -> List[Dict[str, Any]]:
        """Get merged PRs since datetime."""
        url = f'{self.base_url}/repos/{self.owner}/{self.repo}/pulls'

        try:
            response = requests.get(
                url,
                params={
                    'state': 'closed',
                    'since': since.isoformat(),
                    'sort': 'updated',
                    'direction': 'desc',
                },
                headers={'Authorization': f'token {self.token}'},
                timeout=10
            )
            response.raise_for_status()

            prs = response.json()
            return [pr for pr in prs if pr.get('merged_at')]
        except Exception as e:
            print(f'Error fetching PRs: {str(e)}')
            return []

    def get_pr_by_branch(self, branch: str) -> Optional[Dict[str, Any]]:
        """Get PR for a specific branch."""
        url = f'{self.base_url}/repos/{self.owner}/{self.repo}/pulls'

        try:
            response = requests.get(
                url,
                params={'head': f'{self.owner}:{branch}'},
                headers={'Authorization': f'token {self.token}'},
                timeout=10
            )
            response.raise_for_status()

            prs = response.json()
            return prs[0] if prs else None
        except Exception as e:
            print(f'Error fetching PR by branch: {str(e)}')
            return None

    def get_repo_health(self) -> Dict[str, Any]:
        """Get overall repository health metrics."""
        try:
            url = f'{self.base_url}/repos/{self.owner}/{self.repo}'

            response = requests.get(
                url,
                headers={'Authorization': f'token {self.token}'},
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            return {
                'stars': data.get('stargazers_count', 0),
                'forks': data.get('forks_count', 0),
                'open_issues': data.get('open_issues_count', 0),
                'watchers': data.get('watchers_count', 0),
            }
        except Exception as e:
            print(f'Error fetching repo health: {str(e)}')
            return {}
