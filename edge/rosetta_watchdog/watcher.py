"""Directory watcher that monitors for new metadata files and processes them."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Callable, List, Set

from .config import WatchdogConfig, WatchDirectory

logger = logging.getLogger(__name__)


class RestartRequested(Exception):
    """Raised to break out of run_forever so the CLI can re-exec the process
    (used after a remote update or an explicit restart command)."""


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
                logger.info(
                    "Loaded state file: %d previously processed file(s)",
                    len(self._processed),
                )
            except Exception:
                logger.warning(
                    "Could not load state file %s — starting fresh", self._path
                )
        else:
            logger.info("No state file found — starting fresh")

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

    @property
    def count(self) -> int:
        return len(self._processed)


SUPPORTED_EXTENSIONS = (".txrm", ".pca")


class DirectoryWatcher:
    """Polls watch directories for new metadata files (.txrm, .pca)."""

    def __init__(
        self,
        config: WatchdogConfig,
        process_callback: Callable[[str, str], bool],
        heartbeat=None,
        command_handler=None,
        on_loop=None,
    ):
        self._config = config
        self._process = process_callback
        self._state = ProcessedState(config.state_file)
        self._heartbeat = heartbeat
        # command_handler(cmd, watcher) -> True | False | "restart"
        self._command_handler = command_handler
        # on_loop(watcher) called once per poll loop (e.g. periodic auto-update)
        self._on_loop = on_loop
        self._paused = False
        self._total_processed = 0
        self._total_errors = 0
        self._total_skipped_duplicates = 0
        self._cycle_count = 0

    def _find_new_files(self, watch_dir: WatchDirectory) -> List[str]:
        """Walk a directory and return paths of new metadata files."""
        new_files: List[str] = []
        drift_skipped = 0
        total_scanned = 0

        if not Path(watch_dir.path).is_dir():
            logger.debug(
                "Directory does not exist yet: %s (%s)",
                watch_dir.path, watch_dir.machine_name,
            )
            return new_files

        try:
            for root, _, files in os.walk(watch_dir.path):
                for fname in files:
                    if not fname.lower().endswith(SUPPORTED_EXTENSIONS):
                        continue
                    total_scanned += 1

                    is_drift = "drift" in fname.lower()
                    if not self._config.include_drift_files and is_drift:
                        drift_skipped += 1
                        continue

                    full_path = os.path.normpath(os.path.join(root, fname))
                    if not self._state.is_processed(full_path):
                        new_files.append(full_path)
        except PermissionError:
            logger.error(
                "Permission denied scanning %s — check folder permissions",
                watch_dir.path,
            )
        except Exception:
            logger.exception("Error scanning directory %s", watch_dir.path)

        logger.debug(
            "Scanned %s: %d file(s) total, %d new, %d already processed, %d drift skipped",
            watch_dir.path, total_scanned, len(new_files),
            total_scanned - len(new_files) - drift_skipped, drift_skipped,
        )

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
        for i, fpath in enumerate(new_files, 1):
            logger.info(
                "[%d/%d] Processing: %s",
                i, len(new_files), os.path.basename(fpath),
            )
            try:
                t0 = time.monotonic()
                success = self._process(fpath, watch_dir.machine_name)
                elapsed = time.monotonic() - t0

                if success:
                    self._state.mark_processed(fpath)
                    self._total_processed += 1
                    processed += 1
                    logger.info(
                        "[%d/%d] Done: %s (%.1fs)",
                        i, len(new_files), os.path.basename(fpath), elapsed,
                    )
                else:
                    self._total_errors += 1
                    logger.warning(
                        "[%d/%d] Failed: %s (%.1fs)",
                        i, len(new_files), os.path.basename(fpath), elapsed,
                    )
            except Exception:
                self._total_errors += 1
                logger.exception(
                    "[%d/%d] Error processing %s",
                    i, len(new_files), fpath,
                )

        return processed

    def run_once(self) -> int:
        """Run a single scan cycle across all watch directories. Returns total processed."""
        self._cycle_count += 1
        t0 = time.monotonic()
        total = 0

        for wd in self._config.watch_directories:
            total += self._process_directory(wd)

        elapsed = time.monotonic() - t0

        if total > 0:
            logger.info(
                "Cycle #%d complete: %d file(s) processed in %.1fs "
                "(lifetime: %d processed, %d errors, %d in state file)",
                self._cycle_count, total, elapsed,
                self._total_processed, self._total_errors, self._state.count,
            )
        else:
            logger.debug(
                "Cycle #%d: no new files (%.1fs, %d in state file)",
                self._cycle_count, elapsed, self._state.count,
            )

        return total

    def _ack_and_flush(self, command_id) -> None:
        """Ack a command and immediately flush it to the Worker. Used before a
        restart so the command is not re-delivered to the new process."""
        if self._heartbeat is None or command_id is None:
            return
        self._heartbeat.ack(command_id)
        try:
            self._heartbeat.maybe_send(self, state="updating", force=True)
        except Exception:
            pass

    def _dispatch_command(self, cmd: dict) -> None:
        """Execute one remote command. May raise RestartRequested."""
        ctype = (cmd or {}).get("type")
        cid = (cmd or {}).get("id")
        logger.info("Received remote command: %s (id=%s)", ctype, cid)

        if ctype == "pause":
            self._paused = True
            result = True
        elif ctype == "resume":
            self._paused = False
            result = True
        elif ctype == "run-once":
            self.run_once()
            result = True
        elif self._command_handler is not None:
            # reload-config / configure / update-now / restart
            result = self._command_handler(cmd, self)
        else:
            logger.warning("No handler for command %s", ctype)
            result = False

        if result == "restart":
            self._ack_and_flush(cid)
            raise RestartRequested(ctype)
        if result and self._heartbeat is not None:
            self._heartbeat.ack(cid)

    def run_forever(self) -> None:
        """Poll watch directories in a loop until interrupted."""
        dirs_str = ", ".join(
            f"{wd.path} ({wd.machine_name})"
            for wd in self._config.watch_directories
        )
        logger.info("Starting continuous watch — monitoring: %s", dirs_str)
        logger.info("Polling every %ds — press Ctrl+C to stop",
                     self._config.polling_interval_seconds)

        if self._heartbeat is not None:
            self._heartbeat.maybe_send(self, state="running", force=True)

        consecutive_errors = 0
        max_consecutive = 10

        try:
            while True:
                # Heartbeat + remote commands run outside the scan try/except so
                # monitoring and control keep working even if scanning fails.
                if self._heartbeat is not None:
                    try:
                        state = "paused" if self._paused else "running"
                        commands = self._heartbeat.maybe_send(self, state=state, force=True)
                    except RestartRequested:
                        raise
                    except Exception:
                        commands = []
                        logger.debug("Heartbeat error (ignored)", exc_info=True)
                    for cmd in commands or []:
                        self._dispatch_command(cmd)  # may raise RestartRequested

                if self._on_loop is not None:
                    self._on_loop(self)  # periodic auto-update; may raise RestartRequested

                if not self._paused:
                    try:
                        self.run_once()
                        consecutive_errors = 0
                    except KeyboardInterrupt:
                        raise
                    except Exception:
                        consecutive_errors += 1
                        logger.exception(
                            "Unexpected error in scan cycle #%d "
                            "(%d consecutive error(s))",
                            self._cycle_count, consecutive_errors,
                        )
                        if consecutive_errors >= max_consecutive:
                            logger.error(
                                "Too many consecutive errors (%d) — stopping. "
                                "Check directory permissions and network connectivity.",
                                consecutive_errors,
                            )
                            raise

                time.sleep(self._config.polling_interval_seconds)
        except KeyboardInterrupt:
            logger.info(
                "Watchdog stopped by user after %d cycle(s) "
                "(%d processed, %d errors)",
                self._cycle_count, self._total_processed, self._total_errors,
            )
            if self._heartbeat is not None:
                self._heartbeat.maybe_send(self, state="stopped", force=True)
