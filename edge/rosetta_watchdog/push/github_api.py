"""Push parsed metadata JSON to a GitHub repository via the Contents API.

Uses the GitHub REST API (no local git installation required).
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Optional, Tuple

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

    def _get_existing_file(self, remote_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Fetch an existing file's git blob SHA and its sha256 field (if JSON).

        Returns (blob_sha, content_sha256). Either may be None.
        """
        url = self._repo_url(f"/contents/{remote_path}")
        resp = self._session.get(
            url,
            headers=self._auth_headers,
            params={"ref": self._config.branch},
        )
        if resp.status_code != 200:
            return None, None

        data = resp.json()
        blob_sha = data.get("sha")
        content_sha256 = None
        raw_content = data.get("content")
        if raw_content:
            try:
                decoded = base64.b64decode(raw_content)
                existing_meta = json.loads(decoded)
                content_sha256 = existing_meta.get("sha256")
            except Exception:
                pass
        return blob_sha, content_sha256

    def push_file(
        self,
        content: bytes,
        remote_path: str,
        commit_message: str,
        content_sha256: Optional[str] = None,
    ) -> bool:
        """Push a file to the configured GitHub repository.

        If the file already exists on GitHub with the same sha256, the push
        is skipped (duplicate detection).

        Args:
            content: Raw file bytes to upload.
            remote_path: Path within the repo (e.g. ``data/scan.txrm.json``).
            commit_message: Git commit message.
            content_sha256: SHA-256 of the source scan file. When provided,
                the remote file is checked first and the push is skipped if
                the sha256 already matches.

        Returns:
            True on success (or already up-to-date), False on failure.
        """
        token = self._config.token
        if not token:
            logger.error("No GitHub token available (env var: %s)", self._config.token_env)
            return False

        blob_sha, remote_sha256 = self._get_existing_file(remote_path)

        if content_sha256 and remote_sha256 and content_sha256 == remote_sha256:
            logger.info(
                "Skipped %s — identical file already on GitHub (sha256: %s…)",
                remote_path, content_sha256[:12],
            )
            return True

        encoded = base64.b64encode(content).decode("ascii")
        url = self._repo_url(f"/contents/{remote_path}")

        body: dict = {
            "message": commit_message,
            "content": encoded,
            "branch": self._config.branch,
        }

        if blob_sha:
            body["sha"] = blob_sha

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
