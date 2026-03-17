"""Directory watcher that monitors for new .txrm files and processes them."""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from .config import WatchdogConfig, WatchDirectory

logger = logging.getLogger(__name__)


class ProcessedState:
    """Tracks which files have already been processed, persisted to disk."""

    def __init__(self, state_file: str):
        self._path = Path(state_file)
        self._processed: Set[str] = set()
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._processed = set(data)
            except Exception:
                logger.warning("Could not load state file %s, starting fresh", self._path)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(sorted(self._processed), indent=2),
            encoding="utf-8",
        )

    def is_processed(self, path: str) -> bool:
        return os.path.normpath(path) in self._processed

    def mark_processed(self, path: str) -> None:
        self._processed.add(os.path.normpath(path))
        self._save()


class DirectoryWatcher:
    """Polls watch directories for new .txrm files."""

    def __init__(
        self,
        config: WatchdogConfig,
        process_callback,
    ):
        self._config = config
        self._process = process_callback
        self._state = ProcessedState(config.state_file)

    def _find_new_files(self, watch_dir: WatchDirectory) -> List[str]:
        """Walk a directory and return paths of new .txrm files."""
        new_files: List[str] = []
        drift_skipped = 0

        try:
            for root, _, files in os.walk(watch_dir.path):
                for fname in files:
                    if not fname.lower().endswith(".txrm"):
                        continue

                    is_drift = "drift" in fname.lower()
                    if not self._config.include_drift_files and is_drift:
                        drift_skipped += 1
                        continue

                    full_path = os.path.normpath(os.path.join(root, fname))
                    if not self._state.is_processed(full_path):
                        new_files.append(full_path)
        except Exception:
            logger.exception("Error scanning directory %s", watch_dir.path)

        if drift_skipped:
            logger.debug("Skipped %d drift files in %s", drift_skipped, watch_dir.path)

        return new_files

    def _process_directory(self, watch_dir: WatchDirectory) -> int:
        """Process all new files in a single watch directory. Returns count processed."""
        new_files = self._find_new_files(watch_dir)
        if not new_files:
            return 0

        logger.info(
            "Found %d new file(s) in %s (%s)",
            len(new_files), watch_dir.path, watch_dir.machine_name,
        )

        processed = 0
        for fpath in new_files:
            try:
                success = self._process(fpath, watch_dir.machine_name)
                if success:
                    self._state.mark_processed(fpath)
                    processed += 1
                    logger.info("Processed: %s", fpath)
                else:
                    logger.warning("Processing returned failure for %s", fpath)
            except Exception:
                logger.exception("Error processing %s", fpath)

        return processed

    def run_once(self) -> int:
        """Run a single scan cycle across all watch directories. Returns total processed."""
        total = 0
        for wd in self._config.watch_directories:
            total += self._process_directory(wd)
        return total

    def run_forever(self) -> None:
        """Poll watch directories in a loop until interrupted."""
        dirs_str = ", ".join(
            f"{wd.path} ({wd.machine_name})"
            for wd in self._config.watch_directories
        )
        logger.info("Starting watchdog — monitoring: %s", dirs_str)
        logger.info("Polling interval: %ds", self._config.polling_interval_seconds)

        try:
            while True:
                self.run_once()
                time.sleep(self._config.polling_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Watchdog stopped by user")
