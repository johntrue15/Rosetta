"""Remote, channel-based self-update for the Rosetta Watchdog.

Flow:
  1. Ask the Worker (`updates.check_url`) which version this facility should run
     (the Worker maps the facility's channel -> a GitHub release/branch).
  2. If the target is newer than the running version (or an update is forced),
     download the source zip, optionally verify its sha256, extract it, and
     `pip install` the `edge/` package into the current interpreter.
  3. The caller restarts the process (os.execv) so the new code takes effect.

All steps are best-effort and guarded: a failed update logs and leaves the
running watchdog untouched.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from typing import Optional

import requests

from ..config import AuthConfig, UpdatesConfig
from ..identity import machine_id

logger = logging.getLogger(__name__)


def _semver(v: str) -> tuple:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", str(v or ""))
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


class Updater:
    def __init__(self, updates: UpdatesConfig, auth: AuthConfig, current_version: str):
        self._updates = updates
        self._auth = auth
        self._current = current_version

    @property
    def enabled(self) -> bool:
        return bool(self._updates.check_url)

    def _ticket(self) -> Optional[str]:
        return os.environ.get(self._auth.install_ticket_env)

    def check(self) -> Optional[dict]:
        """Return the target descriptor from the Worker, or None on failure."""
        ticket = self._ticket()
        if not ticket:
            return None
        try:
            resp = requests.post(
                self._updates.check_url,
                json={"install_ticket": ticket, "machine_id": machine_id()},
                timeout=20,
            )
            if resp.status_code != 200:
                logger.debug("Version check HTTP %d: %s", resp.status_code, resp.text[:200])
                return None
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.debug("Version check failed (ignored): %s", exc)
            return None

    def is_newer(self, target: dict) -> bool:
        # Branch-tracking targets (source == "branch") carry no comparable
        # version, so they never trigger an automatic update.
        if not target or target.get("source") == "branch":
            return False
        return _semver(target.get("version")) > _semver(self._current)

    def maybe_auto_update(self) -> bool:
        """Check + apply if newer and auto_apply is on. Returns True if applied."""
        if not self.enabled or not self._updates.auto_apply:
            return False
        target = self.check()
        if not target or not self.is_newer(target):
            return False
        logger.info(
            "Update available: %s -> %s (%s). Applying...",
            self._current, target.get("version"), target.get("source"),
        )
        return self.apply(target)

    def update_now(self) -> bool:
        """Force-apply the current channel target regardless of version."""
        if not self.enabled:
            logger.warning("update-now requested but updates.check_url is not configured")
            return False
        target = self.check()
        if not target:
            logger.warning("update-now: could not resolve a target version")
            return False
        logger.info("Forcing update to %s (%s)...", target.get("version"), target.get("source"))
        return self.apply(target)

    def apply(self, target: dict) -> bool:
        zip_url = target.get("zip_url")
        if not zip_url:
            logger.error("Update target missing zip_url")
            return False
        try:
            with tempfile.TemporaryDirectory(prefix="rosetta-update-") as tmp:
                zip_path = os.path.join(tmp, "src.zip")
                logger.info("Downloading update from %s", zip_url)
                with requests.get(zip_url, stream=True, timeout=120) as r:
                    r.raise_for_status()
                    with open(zip_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=65536):
                            f.write(chunk)

                expected = target.get("sha256")
                if expected:
                    actual = self._sha256(zip_path)
                    if actual.lower() != str(expected).lower():
                        logger.error("Update sha256 mismatch (expected %s, got %s) — aborting",
                                     expected, actual)
                        return False
                    logger.info("Update sha256 verified")

                extract_dir = os.path.join(tmp, "extract")
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(extract_dir)

                edge_dir = self._find_edge_dir(extract_dir)
                if not edge_dir:
                    logger.error("Could not find the edge/ package in the downloaded source")
                    return False

                logger.info("Installing update (pip install %s)...", edge_dir)
                proc = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", edge_dir],
                    capture_output=True, text=True,
                )
                if proc.returncode != 0:
                    logger.error("pip install failed (%d): %s", proc.returncode, proc.stderr[-500:])
                    return False

                logger.info("Update installed successfully (%s). Restart pending.", target.get("version"))
                return True
        except Exception:
            logger.exception("Update failed — keeping current version")
            return False

    @staticmethod
    def _sha256(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _find_edge_dir(root: str) -> Optional[str]:
        # GitHub zipballs extract to a single top-level <repo>-<ref>/ dir.
        for entry in os.listdir(root):
            candidate = os.path.join(root, entry, "edge")
            if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "pyproject.toml")):
                return candidate
            if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "setup.py")):
                return candidate
        # Fallback: maybe the zip root *is* the repo.
        candidate = os.path.join(root, "edge")
        if os.path.isdir(candidate):
            return candidate
        return None
