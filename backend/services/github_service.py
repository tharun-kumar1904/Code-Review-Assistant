"""
GitHub API integration service.
Fetches PR data, changed files, and posts review comments.
"""

import httpx
import hashlib
import hmac
from typing import Optional, List, Dict, Any
from config import get_settings
from services.cache_service import CacheService

settings = get_settings()
cache = CacheService()


class GitHubService:
    """Service for interacting with the GitHub API."""

    def __init__(self):
        self.base_url = settings.GITHUB_API_BASE
        self.headers = {
            "Authorization": f"token {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        """Make an authenticated request to the GitHub API."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method,
                f"{self.base_url}{url}",
                headers=self.headers,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        """Fetch pull request details."""
        cache_key = f"pr:{owner}/{repo}#{pr_number}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        data = await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
        await cache.set(cache_key, data, ttl=300)
        return data

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[dict]:
        """Fetch changed files in a pull request."""
        cache_key = f"pr_files:{owner}/{repo}#{pr_number}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        data = await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/files")
        await cache.set(cache_key, data, ttl=300)
        return data

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str = "main") -> str:
        """Fetch file content from a repository."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/contents/{path}",
                    headers={**self.headers, "Accept": "application/vnd.github.v3.raw"},
                    params={"ref": ref},
                )
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError:
            return ""

    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Fetch the raw diff for a pull request."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers={
                    **self.headers,
                    "Accept": "application/vnd.github.v3.diff",
                },
            )
            response.raise_for_status()
            return response.text

    async def post_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        commit_id: str,
        path: str,
        line: int,
    ):
        """Post an inline review comment on a pull request."""
        try:
            await self._request(
                "POST",
                f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
                json={
                    "body": body,
                    "commit_id": commit_id,
                    "path": path,
                    "line": line,
                    "side": "RIGHT",
                },
            )
        except httpx.HTTPStatusError:
            # Fall back to posting a general PR comment
            await self.post_pr_comment(owner, repo, pr_number, f"**{path}:{line}**\n\n{body}")

    async def post_pr_comment(self, owner: str, repo: str, pr_number: int, body: str):
        """Post a general comment on a pull request."""
        await self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )

    async def get_repository(self, owner: str, repo: str) -> dict:
        """Fetch repository metadata."""
        cache_key = f"repo:{owner}/{repo}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        data = await self._request("GET", f"/repos/{owner}/{repo}")
        await cache.set(cache_key, data, ttl=3600)
        return data
