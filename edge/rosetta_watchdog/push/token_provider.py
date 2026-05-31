"""Worker-backed token provider for the Rosetta Watchdog.

Trades an install ticket (issued once during install) for a 1-hour GitHub
App installation token. Caches the token until it's within `_REFRESH_BUFFER`
seconds of expiry and refreshes transparently on demand.

Two operating modes:

- **Worker mode** (preferred): ``auth.token_url`` is set in config and
  ``ROSETTA_INSTALL_TICKET`` (or whatever ``auth.install_ticket_env`` names)
  is present in the environment. The provider POSTs the install ticket to
  the worker and uses the returned installation token.

- **Static-token fallback**: ``ROSETTA_GITHUB_TOKEN`` (or
  ``github.token_env``) is set in the environment. The provider returns
  that token without refreshing. This preserves the legacy PAT-based flow.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests

from ..config import AuthConfig, GitHubConfig

logger = logging.getLogger(__name__)

_REFRESH_BUFFER_SECONDS = 5 * 60


@dataclass
class _CachedToken:
    token: str
    expires_epoch: float


class TokenProvider:
    """Resolves a current GitHub token, refreshing from the Worker as needed."""

    def __init__(self, github: GitHubConfig, auth: AuthConfig):
        self._github = github
        self._auth = auth
        self._cached: Optional[_CachedToken] = None

    @property
    def uses_worker(self) -> bool:
        return bool(self._auth.token_url)

    def get(self, *, force_refresh: bool = False) -> Optional[str]:
        """Return a usable token, refreshing if Worker-backed and stale."""
        if self.uses_worker:
            return self._get_from_worker(force_refresh=force_refresh)
        return os.environ.get(self._github.token_env)

    def invalidate(self) -> None:
        self._cached = None

    def _get_from_worker(self, *, force_refresh: bool) -> Optional[str]:
        now = time.time()
        if (
            not force_refresh
            and self._cached
            and self._cached.expires_epoch - now > _REFRESH_BUFFER_SECONDS
        ):
            return self._cached.token

        ticket = os.environ.get(self._auth.install_ticket_env)
        if not ticket:
            logger.error(
                "Worker auth configured but %s is not set in the environment",
                self._auth.install_ticket_env,
            )
            return None

        try:
            from ..identity import machine_id
            resp = requests.post(
                self._auth.token_url,
                json={"install_ticket": ticket, "machine_id": machine_id()},
                timeout=30,
            )
        except requests.RequestException as exc:
            logger.warning("Worker token refresh failed: %s", exc)
            return self._cached.token if self._cached else None

        if resp.status_code != 200:
            logger.error(
                "Worker token refresh HTTP %d: %s",
                resp.status_code, resp.text[:300],
            )
            return self._cached.token if self._cached else None

        data = resp.json()
        token = data.get("token")
        expires_at = data.get("expires_at")
        if not token or not expires_at:
            logger.error("Worker response missing token/expires_at: %s", data)
            return None

        try:
            expires_epoch = datetime.fromisoformat(
                expires_at.replace("Z", "+00:00")
            ).astimezone(timezone.utc).timestamp()
        except Exception:
            expires_epoch = now + 3300

        self._cached = _CachedToken(token=token, expires_epoch=expires_epoch)
        logger.info(
            "Refreshed GitHub App installation token (expires %s, %.0fs from now)",
            expires_at, expires_epoch - now,
        )
        return token
