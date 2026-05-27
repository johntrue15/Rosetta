"""Push parsed metadata JSON to a GitHub repository via the Contents API.

Uses the GitHub REST API (no local git installation required). Tokens come
from the :class:`TokenProvider`, which transparently refreshes Worker-issued
App installation tokens when they near expiry.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Optional, Tuple

import requests

from ..config import GitHubConfig, AuthConfig
from .token_provider import TokenProvider

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


class GitHubPusher:
    """Pushes files to a GitHub repo using a (rotating) install token or PAT."""

    def __init__(self, config: GitHubConfig, auth: Optional[AuthConfig] = None):
        self._config = config
        self._tokens = TokenProvider(config, auth or AuthConfig())
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    @property
    def token_provider(self) -> TokenProvider:
        return self._tokens

    def _auth_headers(self, *, force_refresh: bool = False) -> dict:
        token = self._tokens.get(force_refresh=force_refresh)
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _repo_url(self, path: str = "") -> str:
        return f"{API_BASE}/repos/{self._config.owner}/{self._config.repo_name}{path}"

    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """Send a request, transparently refreshing the token on 401 once."""
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.update(self._auth_headers())
        resp = self._session.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 401 and self._tokens.uses_worker:
            logger.warning("GitHub returned 401 — forcing token refresh and retrying once")
            self._tokens.invalidate()
            headers.update(self._auth_headers(force_refresh=True))
            resp = self._session.request(method, url, headers=headers, **kwargs)
        return resp

    def _get_existing_file(self, remote_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Fetch an existing file's git blob SHA and its sha256 field (if JSON).

        Returns (blob_sha, content_sha256). Either may be None.
        """
        url = self._repo_url(f"/contents/{remote_path}")
        resp = self._request_with_retry("GET", url, params={"ref": self._config.branch})
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

        Returns True on success (or already up-to-date), False on failure.
        """
        token = self._tokens.get()
        if not token:
            if self._tokens.uses_worker:
                logger.error(
                    "No GitHub token available -- Worker token refresh failed "
                    "(check %s and Worker connectivity)",
                    "ROSETTA_INSTALL_TICKET",
                )
            else:
                logger.error(
                    "No GitHub token available (env var: %s)", self._config.token_env
                )
            return False

        t0 = time.monotonic()
        blob_sha, remote_sha256 = self._get_existing_file(remote_path)
        check_ms = (time.monotonic() - t0) * 1000

        if content_sha256 and remote_sha256 and content_sha256 == remote_sha256:
            logger.info(
                "Skipped %s — identical file already on GitHub "
                "(sha256: %s…, checked in %.0fms)",
                remote_path, content_sha256[:12], check_ms,
            )
            return True

        if blob_sha:
            logger.info("File exists on GitHub (blob sha: %s…) — will update", blob_sha[:12])
        else:
            logger.info("New file — will create %s", remote_path)

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
            t1 = time.monotonic()
            resp = self._request_with_retry("PUT", url, json=body)
            push_ms = (time.monotonic() - t1) * 1000

            if resp.status_code in (200, 201):
                action = "Updated" if blob_sha else "Created"
                logger.info(
                    "%s %s on %s/%s (%.0fms)",
                    action, remote_path,
                    self._config.owner, self._config.repo_name, push_ms,
                )
                return True
            else:
                logger.error(
                    "GitHub API error %d for %s (%.0fms): %s",
                    resp.status_code, remote_path, push_ms,
                    resp.json().get("message", resp.text[:200]),
                )
                return False
        except requests.RequestException:
            logger.exception("Network error pushing %s", remote_path)
            return False
