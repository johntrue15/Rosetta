"""Push parsed metadata JSON to a GitHub repository via the Contents API.

Uses the GitHub REST API (no local git installation required).
"""

from __future__ import annotations

import base64
import logging
from typing import Optional

import requests

from ..config import GitHubConfig

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


class GitHubPusher:
    """Pushes files to a GitHub repo using a Personal Access Token."""

    def __init__(self, config: GitHubConfig):
        self._config = config
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    @property
    def _auth_headers(self) -> dict:
        token = self._config.token
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    def _repo_url(self, path: str = "") -> str:
        return f"{API_BASE}/repos/{self._config.owner}/{self._config.repo_name}{path}"

    def _get_existing_sha(self, remote_path: str) -> Optional[str]:
        """Get the SHA of an existing file so we can update it."""
        url = self._repo_url(f"/contents/{remote_path}")
        resp = self._session.get(
            url,
            headers=self._auth_headers,
            params={"ref": self._config.branch},
        )
        if resp.status_code == 200:
            return resp.json().get("sha")
        return None

    def push_file(
        self,
        content: bytes,
        remote_path: str,
        commit_message: str,
    ) -> bool:
        """Push a file to the configured GitHub repository.

        Args:
            content: Raw file bytes to upload.
            remote_path: Path within the repo (e.g. ``data/scan.txrm.json``).
            commit_message: Git commit message.

        Returns:
            True on success, False on failure.
        """
        token = self._config.token
        if not token:
            logger.error("No GitHub token available (env var: %s)", self._config.token_env)
            return False

        encoded = base64.b64encode(content).decode("ascii")
        url = self._repo_url(f"/contents/{remote_path}")

        body: dict = {
            "message": commit_message,
            "content": encoded,
            "branch": self._config.branch,
        }

        existing_sha = self._get_existing_sha(remote_path)
        if existing_sha:
            body["sha"] = existing_sha

        try:
            resp = self._session.put(url, json=body, headers=self._auth_headers)
            if resp.status_code in (200, 201):
                logger.info("Pushed %s to %s/%s", remote_path,
                            self._config.owner, self._config.repo_name)
                return True
            else:
                logger.error(
                    "GitHub API error %d for %s: %s",
                    resp.status_code, remote_path,
                    resp.json().get("message", resp.text[:200]),
                )
                return False
        except requests.RequestException:
            logger.exception("Network error pushing %s", remote_path)
            return False
