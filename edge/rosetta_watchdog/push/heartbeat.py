"""Fleet monitoring heartbeat reporter.

Periodically POSTs the watchdog's status to the Rosetta Upload Worker
(`/watchdog/heartbeat`) so the org dashboard can show which facilities are
online, their version, recent activity, and watch-directory health.

The heartbeat is best-effort: any network/HTTP failure is logged and
swallowed so monitoring can never take down the watcher. It reuses the same
install ticket as the data-push path (no extra credentials).
"""

from __future__ import annotations

import logging
import os
import platform
import socket
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from ..config import AuthConfig, GitHubConfig, MonitoringConfig

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class HeartbeatReporter:
    """Throttled status reporter for the fleet dashboard."""

    def __init__(
        self,
        monitoring: MonitoringConfig,
        auth: AuthConfig,
        github: GitHubConfig,
        version: str,
    ):
        self._monitoring = monitoring
        self._auth = auth
        self._github = github
        self._version = version
        self._hostname = socket.gethostname()
        self._platform = f"{platform.system()} {platform.release()} ({platform.machine()})"
        self._pid = os.getpid()
        self._started_at = _utcnow_iso()
        self._last_sent = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self._monitoring.heartbeat_url)

    def _ticket(self) -> Optional[str]:
        return os.environ.get(self._auth.install_ticket_env)

    def _build_status(self, watcher, state: str) -> dict:
        watch_dirs = []
        try:
            from pathlib import Path
            for wd in watcher._config.watch_directories:
                watch_dirs.append({"path": wd.path, "ok": Path(wd.path).is_dir()})
        except Exception:
            pass

        return {
            "version": self._version,
            "hostname": self._hostname,
            "platform": self._platform,
            "pid": self._pid,
            "state": state,
            "started_at": self._started_at,
            "last_cycle_at": _utcnow_iso(),
            "cycle_count": getattr(watcher, "_cycle_count", None),
            "processed": getattr(watcher, "_total_processed", None),
            "errors": getattr(watcher, "_total_errors", None),
            "state_count": getattr(getattr(watcher, "_state", None), "count", None),
            "polling_interval": watcher._config.polling_interval_seconds,
            "repo": self._github.repo,
            "watch_dirs": watch_dirs,
        }

    def maybe_send(self, watcher, *, state: str = "running", force: bool = False) -> None:
        """Send a heartbeat if enabled and the throttle interval has elapsed."""
        if not self.enabled:
            return
        now = time.time()
        if not force and (now - self._last_sent) < self._monitoring.interval_seconds:
            return
        self._send(self._build_status(watcher, state))
        self._last_sent = now

    def _send(self, status: dict) -> None:
        ticket = self._ticket()
        if not ticket:
            logger.debug("Heartbeat skipped: no install ticket in %s", self._auth.install_ticket_env)
            return
        try:
            resp = requests.post(
                self._monitoring.heartbeat_url,
                json={"install_ticket": ticket, "status": status},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.debug("Heartbeat HTTP %d: %s", resp.status_code, resp.text[:200])
        except requests.RequestException as exc:
            logger.debug("Heartbeat failed (ignored): %s", exc)
